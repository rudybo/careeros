import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.market_scout import agent as scout
from app.agents.market_scout.agent import ScoutError
from app.agents.cover_letter import agent as cover_letter_agent
from app.agents.cover_letter.agent import CoverLetterError
from app.core.database import AsyncSessionLocal, get_db
from app.repositories.cv_repository import CVRepository
from app.repositories.market_repository import OpportunityRepository, PreferencesRepository
from app.schemas.cv import ParsedCV
from app.schemas.market import (
    JobOpportunityResponse,
    OpportunityStatusUpdate,
    UserPreferencesResponse,
    UserPreferencesUpdate,
)
from app.services import gmail_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["Market Scout"])

_search_running = False
_last_search_error: str | None = None
_last_search_count: int | None = None


def _build_opp_response(opp) -> JobOpportunityResponse:
    reasons = None
    if opp.match_reasons:
        try:
            reasons = json.loads(opp.match_reasons)
        except Exception:
            reasons = [opp.match_reasons]
    return JobOpportunityResponse(
        id=opp.id,
        external_id=opp.external_id,
        source=opp.source,
        title=opp.title,
        company=opp.company,
        location=opp.location,
        url=opp.url,
        salary_min=opp.salary_min,
        salary_max=opp.salary_max,
        work_mode=opp.work_mode,
        match_score=opp.match_score,
        match_reasons=reasons,
        status=opp.status,
        draft_status=opp.draft_status,
        gmail_url=opp.gmail_url,
        found_at=opp.found_at,
    )


async def _run_search(cv_parsed_data: dict) -> None:
    global _search_running, _last_search_error, _last_search_count
    async with AsyncSessionLocal() as session:
        prefs_repo = PreferencesRepository(session)
        opp_repo = OpportunityRepository(session)
        try:
            parsed_cv = ParsedCV(**cv_parsed_data)
            prefs = await prefs_repo.get()
            results = await scout.search(parsed_cv, prefs)
            created, skipped = await opp_repo.upsert_many(results)
            _last_search_count = created
            _last_search_error = None
            logger.info("Market Scout: %d nuove offerte, %d gia presenti", created, skipped)
        except ScoutError as e:
            _last_search_error = str(e)
            logger.error("Market Scout fallito: %s", e)
        except Exception as e:
            _last_search_error = f"Errore inatteso: {e}"
            logger.error("Market Scout errore inatteso: %s", e, exc_info=True)
        finally:
            _search_running = False


@router.get("/preferences", response_model=UserPreferencesResponse | None)
async def get_preferences(db: AsyncSession = Depends(get_db)):
    repo = PreferencesRepository(db)
    prefs = await repo.get()
    if prefs is None:
        return None
    _deserialize_prefs(prefs)
    return prefs


@router.put("/preferences", response_model=UserPreferencesResponse)
async def upsert_preferences(body: UserPreferencesUpdate, db: AsyncSession = Depends(get_db)):
    repo = PreferencesRepository(db)
    prefs = await repo.upsert(body.model_dump(exclude_none=True))
    _deserialize_prefs(prefs)
    return prefs


def _deserialize_prefs(prefs) -> None:
    if prefs.sectors and isinstance(prefs.sectors, str):
        prefs.sectors = json.loads(prefs.sectors)
    if prefs.target_roles and isinstance(prefs.target_roles, str):
        prefs.target_roles = json.loads(prefs.target_roles)


@router.post("/search", status_code=status.HTTP_202_ACCEPTED)
async def start_search(background_tasks: BackgroundTasks, cv_id: int = 1, db: AsyncSession = Depends(get_db)):
    global _search_running
    if _search_running:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ricerca già in corso.")

    cv_repo = CVRepository(db)
    cv = await cv_repo.get_by_id(cv_id)
    if cv is None or not cv.parsed_data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV non trovato o non ancora parsato.")

    _search_running = True
    background_tasks.add_task(_run_search, json.loads(cv.parsed_data))
    return {"status": "searching", "message": "Ricerca offerte avviata. Usa GET /market/opportunities per vedere i risultati."}


@router.get("/search/status")
async def search_status():
    return {"running": _search_running, "last_error": _last_search_error, "last_count": _last_search_count}


@router.get("/opportunities", response_model=list[JobOpportunityResponse])
async def list_opportunities(status_filter: str | None = None, limit: int = 10, db: AsyncSession = Depends(get_db)):
    repo = OpportunityRepository(db)
    # For saved/dismissed show all; for new/all apply limit
    effective_limit = None if status_filter in ("saved", "dismissed", "applied") else limit
    opps = await repo.get_all(status=status_filter, limit=effective_limit)
    return [_build_opp_response(o) for o in opps]


@router.patch("/opportunities/{opp_id}/status", response_model=JobOpportunityResponse)
async def update_opportunity_status(opp_id: int, body: OpportunityStatusUpdate, db: AsyncSession = Depends(get_db)):
    valid = {"new", "saved", "dismissed", "applied"}
    if body.status not in valid:
        raise HTTPException(status_code=422, detail=f"Stato non valido. Valori: {sorted(valid)}")
    repo = OpportunityRepository(db)
    opp = await repo.update_status(opp_id, body.status)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunità non trovata.")
    return _build_opp_response(opp)


@router.post("/opportunities/{opp_id}/draft", status_code=status.HTTP_202_ACCEPTED)
async def create_draft_email(
    opp_id: int,
    background_tasks: BackgroundTasks,
    cv_id: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """Generate a cover letter and create a Gmail draft for the given opportunity."""
    opp_repo = OpportunityRepository(db)
    opp = await opp_repo.get_by_id(opp_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunità non trovata.")
    if opp.draft_status in ("ready", "generating"):
        raise HTTPException(status_code=409, detail="Bozza già creata o in generazione.")

    cv_repo = CVRepository(db)
    cv = await cv_repo.get_by_id(cv_id)
    if cv is None or not cv.parsed_data:
        raise HTTPException(status_code=409, detail="CV non trovato o non ancora parsato.")

    await opp_repo.update_draft_status(opp_id, "generating")
    background_tasks.add_task(
        _run_create_draft,
        opp_id=opp_id,
        cv_parsed_data=json.loads(cv.parsed_data),
        title=opp.title,
        company=opp.company or "Azienda",
        description=opp.description or "",
    )
    return {"status": "generating", "message": "Generazione lettera e bozza Gmail avviata."}


async def _run_create_draft(opp_id: int, cv_parsed_data: dict, title: str, company: str, description: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            repo = OpportunityRepository(session)
            try:
                cv = ParsedCV(**cv_parsed_data)
                letter = await cover_letter_agent.generate(
                    cv=cv,
                    company=company,
                    role=title,
                    job_description=description,
                    optimization=None,
                )
                result = gmail_service.create_draft(
                    to="",
                    subject=letter["subject"],
                    body=letter["full_text"],
                )
                await repo.update_draft(opp_id, result["draft_id"], result["gmail_url"])
                logger.info("Bozza Gmail creata per opportunità %d: %s", opp_id, result["draft_id"])
            except (CoverLetterError, RuntimeError) as e:
                logger.error("Errore creazione bozza per opp %d: %s", opp_id, e)
                await repo.update_draft_status(opp_id, "none")
            except Exception as e:
                logger.error("Errore inatteso creazione bozza per opp %d: %s", opp_id, e, exc_info=True)
                await repo.update_draft_status(opp_id, "none")
    except Exception as outer_e:
        logger.error("Errore critico background task draft opp %d: %s", opp_id, outer_e, exc_info=True)
