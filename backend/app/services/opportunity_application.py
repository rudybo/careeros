"""Collega le offerte del Market (e le bozze Telegram) alle Candidature."""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import JobApplication
from app.repositories.application_repository import ApplicationRepository
from app.repositories.market_repository import OpportunityRepository

logger = logging.getLogger(__name__)


async def record_draft(
    session: AsyncSession, opp_id: int, cv_id: int, result: dict, job_text: str,
) -> JobApplication:
    """Crea (o riusa) la Candidatura dell'offerta e vi salva bozza + PDF allegato."""
    opp = await OpportunityRepository(session).get_by_id(opp_id)
    if opp is None:
        raise ValueError(f"Opportunità {opp_id} non trovata")
    repo = ApplicationRepository(session)
    app = await repo.get_by_opportunity_id(opp_id)
    if app is None:
        app = await repo.create_from_opportunity(
            cv_id=cv_id, opportunity_id=opp_id, company=opp.company or "Azienda", role=opp.title,
            job_description=job_text, source_url=opp.url,
            advertiser_type=result.get("advertiser_type"), contact_email=result.get("contact_email"),
        )
    else:
        await repo.set_meta(app.id, result.get("advertiser_type") or app.advertiser_type,
                            result.get("contact_email") or app.contact_email)
    app = await repo.update_draft(app.id, result["tailored_cv"], result["cover_letter"], result["gmail_url"],
                                thread_id=result.get("thread_id"))
    if app.status == "draft":
        app = await repo.update_status(app.id, "ready")
    await repo.add_document(app.id, "cv_su_misura", result["pdf_filename"], result["pdf_bytes"])
    return app


async def mark_applied(session: AsyncSession, opp_id: int, cv_id: int) -> JobApplication | None:
    """Segna offerta e Candidatura come 'applied' (idempotente). None se l'offerta non esiste."""
    opp = await OpportunityRepository(session).update_status(opp_id, "applied")
    if opp is None:
        return None
    repo = ApplicationRepository(session)
    app = await repo.get_by_opportunity_id(opp_id)
    if app is None:
        app = await repo.create_from_opportunity(
            cv_id=cv_id, opportunity_id=opp_id, company=opp.company or "Azienda", role=opp.title,
            job_description=opp.description or "", source_url=opp.url, advertiser_type=opp.advertiser_type,
        )
    if app.status not in ("applied", "interview", "offer", "rejected"):
        app = await repo.update_status(app.id, "applied")
    return app
