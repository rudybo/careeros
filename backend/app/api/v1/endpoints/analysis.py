import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.career_strategist import agent as career_strategist
from app.agents.career_strategist.agent import CareerStrategistError
from app.core.database import AsyncSessionLocal, get_db
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.cv_repository import CVRepository
from app.schemas.analysis import CareerAnalysis, CareerAnalysisResponse
from app.schemas.cv import ParsedCV

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cv", tags=["Analysis"])


async def _run_analysis(analysis_id: int, cv_parsed_data: dict) -> None:
    async with AsyncSessionLocal() as session:
        repo = AnalysisRepository(session)
        try:
            parsed_cv = ParsedCV(**cv_parsed_data)
            result = await career_strategist.analyze(parsed_cv)
            await repo.update_analysis_data(analysis_id, result)
            logger.info("Analisi completata: analysis_id=%d", analysis_id)
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
    background_tasks.add_task(_run_analysis, record.id, cv_parsed_data)

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
