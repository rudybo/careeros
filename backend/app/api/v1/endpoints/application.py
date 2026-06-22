import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cv_expert import agent as cv_expert
from app.agents.cv_expert.agent import CVExpertError
from app.core.database import AsyncSessionLocal, get_db
from app.repositories.application_repository import ApplicationRepository
from app.repositories.cv_repository import CVRepository
from app.schemas.application import (
    CVOptimization,
    JobApplicationCreate,
    JobApplicationDetailResponse,
    JobApplicationResponse,
    JobApplicationStatusUpdate,
)
from app.schemas.cv import ParsedCV

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["Applications"])


async def _run_cv_optimization(app_id: int, cv_parsed_data: dict, job_description: str) -> None:
    async with AsyncSessionLocal() as session:
        repo = ApplicationRepository(session)
        try:
            parsed_cv = ParsedCV(**cv_parsed_data)
            result = await cv_expert.analyze(parsed_cv, job_description)
            await repo.update_optimization(app_id, result)
            logger.info("CV Expert completato: application_id=%d match_score=%s", app_id, result.get("match_score"))
        except Exception as e:
            await repo.update_status(app_id, "error")
            logger.error("CV Expert fallito: application_id=%d error=%s", app_id, e, exc_info=True)


def _build_detail(record) -> JobApplicationDetailResponse:
    optimization = None
    if record.optimization_data:
        optimization = CVOptimization(**json.loads(record.optimization_data))
    return JobApplicationDetailResponse(
        id=record.id,
        cv_id=record.cv_id,
        company=record.company,
        role=record.role,
        job_description=record.job_description,
        status=record.status,
        optimization=optimization,
        applied_at=record.applied_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/", response_model=JobApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(body: JobApplicationCreate, db: AsyncSession = Depends(get_db)):
    cv_repo = CVRepository(db)
    cv = await cv_repo.get_by_id(body.cv_id)
    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trovato.")
    if cv.status != "parsed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Il CV deve essere in stato 'parsed'. Stato attuale: '{cv.status}'.",
        )

    repo = ApplicationRepository(db)
    record = await repo.create(
        cv_id=body.cv_id,
        company=body.company,
        role=body.role,
        job_description=body.job_description,
    )
    logger.info("Candidatura creata: id=%d company=%s role=%s", record.id, record.company, record.role)
    return record


@router.post("/{app_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_application(
    app_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    repo = ApplicationRepository(db)
    record = await repo.get_by_id(app_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    if record.status == "analyzing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Analisi già in corso.")

    cv_repo = CVRepository(db)
    cv = await cv_repo.get_by_id(record.cv_id)
    if cv is None or not cv.parsed_data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV non ancora parsato.")

    await repo.update_status(app_id, "analyzing")
    cv_parsed_data = json.loads(cv.parsed_data)
    background_tasks.add_task(_run_cv_optimization, app_id, cv_parsed_data, record.job_description)

    return {
        "application_id": app_id,
        "status": "analyzing",
        "message": "Analisi CV avviata. Usa GET /applications/{id} per monitorare lo stato.",
    }


@router.patch("/{app_id}/status", response_model=JobApplicationResponse)
async def update_status(app_id: int, body: JobApplicationStatusUpdate, db: AsyncSession = Depends(get_db)):
    valid_statuses = {"draft", "ready", "applied", "interview", "offer", "rejected"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Stato non valido. Valori permessi: {sorted(valid_statuses)}",
        )
    repo = ApplicationRepository(db)
    record = await repo.update_status(app_id, body.status)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    return record


@router.get("/", response_model=list[JobApplicationResponse])
async def list_applications(db: AsyncSession = Depends(get_db)):
    repo = ApplicationRepository(db)
    return await repo.get_all()


@router.get("/{app_id}", response_model=JobApplicationDetailResponse)
async def get_application(app_id: int, db: AsyncSession = Depends(get_db)):
    repo = ApplicationRepository(db)
    record = await repo.get_by_id(app_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    return _build_detail(record)
