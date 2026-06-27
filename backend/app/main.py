import logging
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router
from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def _reset_stuck_drafts() -> None:
    """Reset any 'generating' draft statuses left over from a previous crashed run."""
    from sqlalchemy import update
    from app.models.market import JobOpportunity
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(JobOpportunity)
            .where(JobOpportunity.draft_status == "generating")
            .values(draft_status="none")
        )
        await session.commit()


async def _scheduled_market_search() -> None:
    """Ricerca offerte automatica (scheduler). Logga avvio/esito, registra lo
    stato persistente e manda una conferma su Telegram (anche con 0 nuove)."""
    import json
    from datetime import datetime
    from app.agents.market_scout import agent as scout
    from app.core import task_state
    from app.repositories.cv_repository import CVRepository
    from app.repositories.market_repository import OpportunityRepository, PreferencesRepository
    from app.schemas.cv import ParsedCV
    from app.services import telegram_service

    now = datetime.now(ZoneInfo("Europe/Rome")).strftime("%H:%M")
    logger.info("Iris scheduler: AVVIO ricerca automatica (%s)", now)
    async with AsyncSessionLocal() as session:
        cv_repo = CVRepository(session)
        cvs = await cv_repo.get_all()
        parsed = next((c for c in cvs if c.status == "parsed" and c.parsed_data), None)
        if not parsed:
            logger.warning("Iris scheduler: nessun CV parsato trovato, skip.")
            task_state.record_search(trigger="auto", error="nessun CV parsato")
            await telegram_service.send_text(f"⚠️ Ricerca automatica {now}: nessun CV parsato, saltata.")
            return
        prefs_repo = PreferencesRepository(session)
        opp_repo = OpportunityRepository(session)
        try:
            cv = ParsedCV(**json.loads(parsed.parsed_data))
            prefs = await prefs_repo.get()
            results = await scout.search(cv, prefs)
            created, skipped = await opp_repo.upsert_many(results)
            logger.info("Iris scheduler: COMPLETATA — %d nuove, %d già presenti", created, skipped)
            task_state.record_search(trigger="auto", created=created, skipped=skipped)
            sent = await telegram_service.notify_new_opportunities()
            msg = f"🔍 Ricerca automatica {now}: <b>{created}</b> nuove, {skipped} già viste"
            if sent:
                msg += f" · {sent} sopra soglia inviate ⬆️"
            await telegram_service.send_text(msg)
        except Exception as e:
            logger.error("Iris scheduler errore: %s", e, exc_info=True)
            task_state.record_search(trigger="auto", error=str(e))
            await telegram_service.send_text(f"⚠️ Ricerca automatica {now} non riuscita: {str(e)[:150]}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _reset_stuck_drafts()
    # Fuso esplicito: il server gira in UTC, ma vogliamo 08:00 e 19:00 ITALIANE
    scheduler = AsyncIOScheduler(timezone=ZoneInfo("Europe/Rome"))
    scheduler.add_job(_scheduled_market_search, "cron", hour=8,  minute=0, id="iris_morning")
    scheduler.add_job(_scheduled_market_search, "cron", hour=19, minute=0, id="iris_evening")
    scheduler.start()
    app.state.scheduler = scheduler  # per l'health-check /system/health
    logger.info("Iris scheduler avviata: 08:00 e 19:00 (Europe/Rome)")

    import asyncio
    telegram_task = asyncio.create_task(_telegram_supervisor())

    yield

    telegram_task.cancel()
    scheduler.shutdown(wait=False)


async def _telegram_supervisor() -> None:
    """Tiene vivo il poller Telegram: se crasha (eccezione non gestita) lo
    riavvia, così non muore in silenzio. Esce solo se cancellato allo shutdown."""
    import asyncio
    from app.services import telegram_service
    while True:
        try:
            await telegram_service.poll_loop()
            return  # ritorno pulito (token assente o cancellazione interna)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error("Telegram poller crashato, riavvio tra 10s: %s", e, exc_info=True)
            await asyncio.sleep(10)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered career platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
