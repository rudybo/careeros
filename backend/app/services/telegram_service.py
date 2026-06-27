"""Notifiche Telegram delle offerte sopra soglia, con bottoni azione.
Funziona in sola uscita (niente webhook): i click sui bottoni vengono letti
da un poller separato che chiama getUpdates."""
import datetime
import html
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Timestamp dell'ultimo giro di polling riuscito: serve all'health-check per
# capire se il loop è vivo (si aggiorna ~ogni 25-35s).
_last_poll_at: datetime.datetime | None = None


def poller_status() -> dict:
    """Stato del poller Telegram per l'health-check."""
    enabled = bool(settings.telegram_bot_token)
    ago = None
    alive = False
    if _last_poll_at is not None:
        ago = (datetime.datetime.now(datetime.timezone.utc) - _last_poll_at).total_seconds()
        alive = ago < 90  # un ciclo è ~25-35s; oltre 90s lo consideriamo bloccato
    return {
        "enabled": enabled,
        "last_poll_at": _last_poll_at.isoformat() if _last_poll_at else None,
        "seconds_ago": round(ago) if ago is not None else None,
        "alive": alive,
    }


async def _call(method: str, payload: dict, timeout: float = 20) -> dict | None:
    if not settings.telegram_bot_token:
        return None
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if not data.get("ok"):
                logger.warning("Telegram %s error: %s", method, data.get("description"))
            return data
    except Exception as e:
        logger.warning("Telegram %s fallito: %s", method, e)
        return None


def _format(opp) -> str:
    """Costruisce il testo HTML del messaggio per un'offerta."""
    esc = html.escape
    lines = [f"🎯 <b>Nuova offerta</b> · match {opp.match_score or 0}%", ""]
    lines.append(f"<b>{esc(opp.title or 'Senza titolo')}</b>")
    loc = " · ".join(esc(x) for x in [opp.company, opp.location] if x)
    if loc:
        lines.append(loc)
    if opp.salary_min or opp.salary_max:
        lines.append(f"💰 {opp.salary_min or '?'}–{opp.salary_max or '?'} €/anno")
    if opp.source:
        lines.append(f"🔍 fonte: {esc(opp.source)}")
    return "\n".join(lines)


async def send_opportunity(opp) -> None:
    """Invia la notifica di un'offerta con i 3 bottoni azione (+ link)."""
    buttons = [[
        {"text": "📝 Genera bozza", "callback_data": f"draft:{opp.id}"},
        {"text": "🔖 Salva", "callback_data": f"save:{opp.id}"},
        {"text": "🗑 Scarta", "callback_data": f"dismiss:{opp.id}"},
    ]]
    if opp.url:
        buttons.append([{"text": "🔗 Vedi annuncio", "url": opp.url}])

    await _call("sendMessage", {
        "chat_id": settings.telegram_chat_id,
        "text": _format(opp),
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": buttons},
    })


async def send_text(text: str) -> None:
    """Messaggio semplice (per conferme/errori dei bottoni)."""
    await _call("sendMessage", {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
    })


async def notify_new_opportunities() -> int:
    """Invia su Telegram le nuove offerte sopra soglia non ancora notificate.
    Da chiamare dopo ogni ricerca (scheduler o manuale). Ritorna quante inviate."""
    if not settings.telegram_bot_token:
        return 0
    from app.core.database import AsyncSessionLocal
    from app.repositories.market_repository import OpportunityRepository
    sent = 0
    async with AsyncSessionLocal() as s:
        repo = OpportunityRepository(s)
        opps = await repo.get_unnotified_above(settings.telegram_min_score)
        for opp in opps:
            await send_opportunity(opp)
            await repo.mark_notified(opp.id)
            sent += 1
    if sent:
        logger.info("Telegram: inviate %d nuove offerte sopra soglia (>=%d)", sent, settings.telegram_min_score)
    return sent


# ── Poller: legge i click sui bottoni (long-polling, niente webhook) ──────────

async def _answer_callback(cb_id: str, text: str = "") -> None:
    await _call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})


async def _do_draft(opp_id: int) -> None:
    import json
    from app.core.database import AsyncSessionLocal
    from app.repositories.market_repository import OpportunityRepository
    from app.repositories.cv_repository import CVRepository
    from app.api.v1.endpoints.market import _run_create_draft

    async with AsyncSessionLocal() as s:
        opp = await OpportunityRepository(s).get_by_id(opp_id)
        cv = await CVRepository(s).get_by_id(1)
        if opp is None or cv is None or not cv.parsed_data:
            await send_text("⚠️ Non riesco a generare la bozza (offerta o CV mancante).")
            return
        if opp.draft_status == "ready" and opp.gmail_url:
            await send_text(f"📝 Bozza già pronta: {opp.gmail_url}")
            return
        await OpportunityRepository(s).update_draft_status(opp_id, "generating")
        title, company = opp.title, opp.company or "Azienda"
        description = opp.description or ""
        parsed = json.loads(cv.parsed_data)

    await _run_create_draft(opp_id=opp_id, cv_parsed_data=parsed, title=title, company=company, description=description)

    async with AsyncSessionLocal() as s:
        opp = await OpportunityRepository(s).get_by_id(opp_id)
    if opp and opp.draft_status == "ready" and opp.gmail_url:
        await send_text(f"✅ Bozza pronta su Gmail:\n{opp.gmail_url}")
    else:
        await send_text("⚠️ La generazione della bozza non è riuscita.")


async def _handle_callback(cb: dict) -> None:
    cb_id = cb.get("id")
    data = cb.get("data", "") or ""
    action, _, sid = data.partition(":")
    try:
        opp_id = int(sid)
    except ValueError:
        await _answer_callback(cb_id)
        return

    from app.core.database import AsyncSessionLocal
    from app.repositories.market_repository import OpportunityRepository

    if action == "save":
        async with AsyncSessionLocal() as s:
            await OpportunityRepository(s).update_status(opp_id, "saved")
        await _answer_callback(cb_id, "🔖 Salvata")
        await send_text("🔖 Offerta salvata.")
    elif action == "dismiss":
        async with AsyncSessionLocal() as s:
            await OpportunityRepository(s).update_status(opp_id, "dismissed")
        await _answer_callback(cb_id, "🗑 Scartata")
        await send_text("🗑 Offerta scartata.")
    elif action == "draft":
        await _answer_callback(cb_id, "📝 Genero la bozza...")
        await _do_draft(opp_id)
    else:
        await _answer_callback(cb_id)


async def poll_loop() -> None:
    """Loop di long-polling: gestisce i click sui bottoni finché vive l'app."""
    import asyncio
    if not settings.telegram_bot_token:
        logger.info("Telegram: token assente, poller non avviato.")
        return
    logger.info("Telegram poller avviato.")
    # Salta gli update arretrati: riparti dall'ultimo
    offset = 0
    init = await _call("getUpdates", {"offset": -1})
    if init and init.get("result"):
        offset = init["result"][-1]["update_id"] + 1
    while True:
        try:
            data = await _call(
                "getUpdates",
                {"offset": offset, "timeout": 25, "allowed_updates": ["callback_query"]},
                timeout=35,
            )
            global _last_poll_at
            _last_poll_at = datetime.datetime.now(datetime.timezone.utc)  # battito per l'health-check
            if data and data.get("ok"):
                for upd in data["result"]:
                    offset = upd["update_id"] + 1
                    cb = upd.get("callback_query")
                    if cb:
                        await _handle_callback(cb)
        except asyncio.CancelledError:
            logger.info("Telegram poller fermato.")
            break
        except Exception as e:
            logger.warning("Telegram poll error: %s", e)
            await asyncio.sleep(5)
