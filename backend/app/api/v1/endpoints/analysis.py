import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.career_strategist import agent as career_strategist
from app.agents.career_strategist.agent import CareerStrategistError
from app.core.database import AsyncSessionLocal, get_db
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.ats_repository import AtsKeywordRepository
from app.repositories.cv_repository import CVRepository
from app.repositories.roadmap_repository import RoadmapRepository
from app.schemas.analysis import (
    AtsKeywordItemResponse,
    AtsKeywordItemUpdate,
    CareerAnalysis,
    CareerAnalysisResponse,
    RoadmapItemResponse,
    RoadmapItemUpdate,
)
from app.schemas.cv import ParsedCV

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cv", tags=["Analysis"])


async def _run_analysis(analysis_id: int, cv_id: int, cv_parsed_data: dict) -> None:
    async with AsyncSessionLocal() as session:
        repo = AnalysisRepository(session)
        roadmap_repo = RoadmapRepository(session)
        ats_repo = AtsKeywordRepository(session)
        try:
            parsed_cv = ParsedCV(**cv_parsed_data)
            # Lista di carriera (unica): attività fatte/annullate e keyword già gestite informano Minerva
            completed, dismissed = await roadmap_repo.get_done_and_dismissed()
            handled_ats = await ats_repo.get_handled()
            result = await career_strategist.analyze(parsed_cv, completed, dismissed, handled_ats)
            await repo.update_analysis_data(analysis_id, result)

            # Testo del CV per l'auto-rilevamento delle keyword
            cv = await CVRepository(session).get_by_id(cv_id)
            cv_text = (cv.raw_text if cv and cv.raw_text else json.dumps(cv_parsed_data, ensure_ascii=False))

            # Auto-rilevamento: ciò che hai inserito nel nuovo CV risulta "aggiunto"
            auto = await ats_repo.mark_present_as_added(cv_text)
            # La roadmap riflette l'ultima analisi: i 'todo' vengono sostituiti
            # (fatti/annullati restano nello storico e non vengono riproposti)
            added = await roadmap_repo.replace_todos(cv_id, result.get("roadmap", []))
            added_ats = await ats_repo.replace_todos(cv_id, result.get("ats_keywords", []), cv_text)
            logger.info("Analisi completata: analysis_id=%d, +%d attività, +%d keyword (auto-aggiunte %d)",
                        analysis_id, added, added_ats, auto)
        except Exception as e:
            await repo.update_status(analysis_id, "error")
            logger.error("Analisi fallita: analysis_id=%d error=%s", analysis_id, e, exc_info=True)


def _build_response(record) -> CareerAnalysisResponse:
    analysis = None
    if record.analysis_data:
        analysis = CareerAnalysis(**json.loads(record.analysis_data))
    return CareerAnalysisResponse(
        id=record.id,
        cv_id=record.cv_id,
        status=record.status,
        analysis=analysis,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/{cv_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    cv_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    cv_repo = CVRepository(db)
    cv = await cv_repo.get_by_id(cv_id)

    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trovato.")

    if cv.status != "parsed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Il CV deve essere in stato 'parsed' prima di poter essere analizzato. Stato attuale: '{cv.status}'.",
        )

    analysis_repo = AnalysisRepository(db)
    record = await analysis_repo.create(cv_id=cv_id)
    await analysis_repo.update_status(record.id, "analyzing")

    cv_parsed_data = json.loads(cv.parsed_data)
    background_tasks.add_task(_run_analysis, record.id, cv_id, cv_parsed_data)

    logger.info("Analisi avviata in background: cv_id=%d analysis_id=%d", cv_id, record.id)
    return {
        "analysis_id": record.id,
        "cv_id": cv_id,
        "status": "analyzing",
        "message": "Analisi avviata. Usa GET /cv/{cv_id}/analysis/{analysis_id} per monitorare lo stato.",
    }


@router.get("/{cv_id}/analysis/{analysis_id}", response_model=CareerAnalysisResponse)
async def get_analysis(cv_id: int, analysis_id: int, db: AsyncSession = Depends(get_db)):
    repo = AnalysisRepository(db)
    record = await repo.get_by_id(analysis_id)

    if record is None or record.cv_id != cv_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analisi non trovata.")

    return _build_response(record)


@router.get("/{cv_id}/analysis", response_model=list[CareerAnalysisResponse])
async def list_analyses(cv_id: int, db: AsyncSession = Depends(get_db)):
    repo = AnalysisRepository(db)
    records = await repo.get_all_by_cv(cv_id)
    return [_build_response(r) for r in records]


@router.get("/{cv_id}/roadmap", response_model=list[RoadmapItemResponse])
async def get_roadmap(cv_id: int, db: AsyncSession = Depends(get_db)):
    """Checklist persistente del CV. Se vuota ma esiste un'analisi con roadmap,
    la popola al volo (backfill per analisi generate prima della feature)."""
    repo = RoadmapRepository(db)
    items = await repo.get_all()
    if not items:
        analysis_repo = AnalysisRepository(db)
        latest = await analysis_repo.get_latest_by_cv(cv_id)
        if latest and latest.analysis_data:
            roadmap = json.loads(latest.analysis_data).get("roadmap", [])
            if roadmap:
                await repo.merge_steps(cv_id, roadmap)
                items = await repo.get_all()
    return items


@router.patch("/{cv_id}/roadmap/{item_id}", response_model=RoadmapItemResponse)
async def update_roadmap_item(
    cv_id: int,
    item_id: int,
    body: RoadmapItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    if body.status not in {"todo", "done", "dismissed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stato non valido.")
    repo = RoadmapRepository(db)
    item = await repo.set_status(item_id, body.status)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attività non trovata.")
    return item


@router.get("/{cv_id}/ats-keywords", response_model=list[AtsKeywordItemResponse])
async def get_ats_keywords(cv_id: int, db: AsyncSession = Depends(get_db)):
    """Checklist persistente delle keyword ATS. Backfill dall'ultima analisi se vuota."""
    repo = AtsKeywordRepository(db)
    items = await repo.get_all()
    if not items:
        analysis_repo = AnalysisRepository(db)
        latest = await analysis_repo.get_latest_by_cv(cv_id)
        if latest and latest.analysis_data:
            keywords = json.loads(latest.analysis_data).get("ats_keywords", [])
            if keywords:
                await repo.replace_todos(cv_id, keywords)
                items = await repo.get_all()
    return items


@router.patch("/{cv_id}/ats-keywords/{item_id}", response_model=AtsKeywordItemResponse)
async def update_ats_keyword(
    cv_id: int,
    item_id: int,
    body: AtsKeywordItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    if body.status not in {"todo", "added", "ignored", "gap"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stato non valido.")
    repo = AtsKeywordRepository(db)
    item = await repo.set_status(item_id, body.status)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword non trovata.")
    return item
