"""Rileva l'invio delle bozze Gmail create da CareerOS e segna la Candidatura."""
import asyncio
import html
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import JobApplication
from app.repositories.application_repository import ApplicationRepository
from app.repositories.market_repository import OpportunityRepository
from app.services import gmail_service, telegram_service

logger = logging.getLogger(__name__)


async def get_candidates(session: AsyncSession, app_id: int | None = None) -> list[JobApplication]:
    """Candidature con bozza pronta non ancora segnate come inviate."""
    q = select(JobApplication).where(
        JobApplication.draft_status == "ready",
        JobApplication.draft_url.is_not(None),
        JobApplication.status.in_(("draft", "ready")),
    )
    if app_id is not None:
        q = q.where(JobApplication.id == app_id)
    return list((await session.execute(q.order_by(JobApplication.id))).scalars().all())


async def check_sent_applications(session: AsyncSession, app_id: int | None = None) -> list[dict]:
    """Controlla su Gmail se le bozze sono state inviate; ritorna le nuove rilevate."""
    done: list[dict] = []
    try:
        candidates = await get_candidates(session, app_id)
        if not candidates:
            return done
        service = await asyncio.to_thread(gmail_service.get_gmail_service)
        repo = ApplicationRepository(session)
        for cand in candidates:
            aid, company, role = cand.id, cand.company, cand.role
            opp_id, draft_url = cand.opportunity_id, cand.draft_url
            thread_id = cand.gmail_thread_id
            if not thread_id:
                thread_id = await asyncio.to_thread(gmail_service.thread_id_from_draft_url, service, draft_url)
                if not thread_id:
                    continue
                await repo.set_thread_id(aid, thread_id)
            sent_at = await asyncio.to_thread(gmail_service.get_sent_time, service, thread_id)
            if sent_at is None:
                continue
            await repo.mark_sent(aid, sent_at)
            if opp_id is not None:
                await OpportunityRepository(session).update_status(opp_id, "applied")
            done.append({"application_id": aid, "company": company, "role": role, "sent_at": sent_at})
            try:
                await telegram_service.send_text(
                    f"✅ Rilevato invio: {html.escape(role)} @ {html.escape(company)} — segnata come candidatura"
                )
            except Exception:
                logger.warning("Notifica Telegram invio fallita: application_id=%d", aid, exc_info=True)
    except Exception as e:
        logger.warning("Controllo invii Gmail fallito: %s", e, exc_info=True)
        try:
            await session.rollback()
        except Exception:
            pass
    return done
