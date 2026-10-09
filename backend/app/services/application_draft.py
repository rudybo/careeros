"""Pipeline annuncio → CV adattato + lettera + bozza Gmail con PDF allegato."""
import asyncio
import json
import logging
import re

from app.agents.cover_letter import agent as cover_letter_agent
from app.agents.cv_tailor import agent as cv_tailor
from app.agents.job_parser import agent as job_parser
from app.core.database import AsyncSessionLocal
from app.repositories.application_repository import ApplicationRepository
from app.repositories.cv_repository import CVRepository
from app.schemas.application import CVOptimization
from app.schemas.cv import ParsedCV
from app.services import gmail_service
from app.services.cv_pdf import render_cv_pdf
from app.services.job_fetcher import JobFetchError, extract_email, fetch_job_posting

logger = logging.getLogger(__name__)


async def resolve_job_text(url: str | None, fallback: str) -> tuple[str, bool]:
    """Prova a scaricare l'annuncio completo dal link; mai solleva per problemi di fetch."""
    if not url:
        return fallback, False
    try:
        fetched = await fetch_job_posting(url)
    except JobFetchError as e:
        logger.info("Annuncio completo non disponibile (%s): uso l'estratto", e)
        return fallback, False
    if fetched and len(fetched) > len(fallback):
        return fetched, True
    return fallback, False


def _pdf_filename(full_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", full_name).strip("_") or "CV"
    return f"CV_{safe}.pdf"


async def build_tailored_draft(
    cv: ParsedCV,
    company: str,
    role: str,
    job_text: str,
    advertiser_type: str | None,
    contact_email: str | None,
    optimization: CVOptimization | None = None,
) -> dict:
    if advertiser_type is None:
        try:
            advertiser_type = (await job_parser.parse(job_text)).advertiser_type
        except job_parser.JobParserError as e:
            logger.warning("Rilevamento tipo inserzionista fallito, procedo senza: %s", e)
    contact_email = contact_email or extract_email(job_text)

    tailored = await cv_tailor.tailor(cv, job_text)
    letter = await cover_letter_agent.generate(
        cv=tailored, company=company, role=role, job_description=job_text,
        optimization=optimization, advertiser_type=advertiser_type,
    )
    pdf = await asyncio.to_thread(render_cv_pdf, tailored)
    draft = await asyncio.to_thread(
        gmail_service.create_draft,
        to=contact_email or "",
        subject=letter["subject"],
        body=letter["full_text"],
        attachments=[(_pdf_filename(cv.full_name), pdf)],
    )
    return {
        "tailored_cv": tailored.model_dump(),
        "cover_letter": letter,
        "draft_id": draft["draft_id"],
        "gmail_url": draft["gmail_url"],
        "advertiser_type": advertiser_type,
        "contact_email": contact_email,
    }


async def run_application_draft(app_id: int) -> None:
    """Background task del flusso Candidature: salva stato e risultati sul record."""
    async with AsyncSessionLocal() as session:
        repo = ApplicationRepository(session)
        try:
            record = await repo.get_by_id(app_id)
            if record is None:
                logger.warning("Bozza su misura: application_id=%d non trovata", app_id)
                return
            cv_row = await CVRepository(session).get_by_id(record.cv_id)
            optimization = CVOptimization(**json.loads(record.optimization_data)) if record.optimization_data else None
            res = await build_tailored_draft(
                ParsedCV(**json.loads(cv_row.parsed_data)), record.company, record.role,
                record.job_description, record.advertiser_type, record.contact_email, optimization,
            )
            await repo.set_meta(app_id, res["advertiser_type"], res["contact_email"])
            await repo.update_draft(app_id, res["tailored_cv"], res["cover_letter"], res["gmail_url"])
            logger.info("Bozza su misura creata: application_id=%d draft_id=%s", app_id, res["draft_id"])
        except Exception as e:  # CVTailorError, CoverLetterError, RuntimeError (Gmail), ...
            logger.error("Bozza su misura fallita: application_id=%d error=%s", app_id, e, exc_info=True)
            try:
                await session.rollback()
                await repo.set_draft_status(app_id, "error")
            except Exception:
                logger.error("Impossibile salvare lo stato 'error': application_id=%d", app_id, exc_info=True)
