import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cover_letter import agent as cover_letter_agent
from app.agents.cover_letter.agent import CoverLetterError
from app.agents.cv_expert import agent as cv_expert
from app.agents.cv_expert.agent import CVExpertError
from app.agents.job_parser import agent as job_parser
from app.core.database import AsyncSessionLocal, get_db
from app.repositories.application_repository import ApplicationRepository
from app.repositories.cv_repository import CVRepository
from app.schemas.application import (
    CoverLetter,
    CVOptimization,
    DocumentMeta,
    JobApplicationCreate,
    JobApplicationDetailResponse,
    JobApplicationResponse,
    JobApplicationStatusUpdate,
    JobApplicationUpdate,
)
from app.schemas.cv import ParsedCV
from app.services.application_draft import run_application_draft
from app.services.sent_check import check_sent_applications, get_candidates
from app.services.job_fetcher import JobFetchError, fetch_job_posting

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


async def _run_cover_letter(app_id: int, cv_parsed_data: dict, company: str, role: str, job_description: str, optimization_data: dict | None) -> None:
    async with AsyncSessionLocal() as session:
        repo = ApplicationRepository(session)
        try:
            parsed_cv = ParsedCV(**cv_parsed_data)
            optimization = CVOptimization(**optimization_data) if optimization_data else None
            result = await cover_letter_agent.generate(parsed_cv, company, role, job_description, optimization)
            await repo.update_cover_letter(app_id, result)
            logger.info("Cover Letter completata: application_id=%d", app_id)
        except Exception as e:
            await repo.set_cover_letter_status(app_id, "error")
            logger.error("Cover Letter fallita: application_id=%d error=%s", app_id, e, exc_info=True)


def _build_detail(record, documents: list | None = None) -> JobApplicationDetailResponse:
    optimization = None
    if record.optimization_data:
        optimization = CVOptimization(**json.loads(record.optimization_data))

    cover_letter = None
    if record.cover_letter:
        cover_letter = CoverLetter(**json.loads(record.cover_letter))

    status_history = json.loads(record.status_history) if record.status_history else []

    return JobApplicationDetailResponse(
        id=record.id,
        cv_id=record.cv_id,
        company=record.company,
        role=record.role,
        job_description=record.job_description,
        status=record.status,
        status_history=status_history,
        optimization=optimization,
        cover_letter=cover_letter,
        cover_letter_status=record.cover_letter_status or "idle",
        source_url=record.source_url,
        advertiser_type=record.advertiser_type,
        contact_email=record.contact_email,
        tailored_cv=ParsedCV(**json.loads(record.tailored_cv)) if record.tailored_cv else None,
        draft_url=record.draft_url,
        draft_status=record.draft_status or "idle",
        documents=[DocumentMeta.model_validate(d) for d in (documents or [])],
        sent_at=record.sent_at,
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

    job_text = body.job_description if (body.job_description or "").strip() else ""
    company, role = body.company, body.role
    advertiser_type, contact_email = body.advertiser_type, body.contact_email

    if not job_text:
        try:
            job_text = await fetch_job_posting(body.source_url)
        except JobFetchError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    if body.source_url or not (company and role):
        try:
            meta = await job_parser.parse(job_text)
        except job_parser.JobParserError as e:
            logger.warning("Job parser fallito: %s", e)
            meta = job_parser.JobMeta()
        company = company or meta.company
        role = role or meta.role
        advertiser_type = advertiser_type or meta.advertiser_type
        contact_email = contact_email or meta.contact_email

    if not (company and role):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Non riesco a ricavare azienda e ruolo dall'annuncio: compilali a mano.",
        )

    repo = ApplicationRepository(db)
    record = await repo.create(
        cv_id=body.cv_id,
        company=company,
        role=role,
        job_description=job_text,
        source_url=body.source_url,
        advertiser_type=advertiser_type,
        contact_email=contact_email,
    )
    logger.info("Candidatura creata: id=%d company=%s role=%s", record.id, record.company, record.role)
    return record


@router.post("/check-sent")
async def check_sent_all(db: AsyncSession = Depends(get_db)):
    """Controlla su Gmail quali bozze risultano inviate (tutte le candidabili)."""
    checked = len(await get_candidates(db))
    sent = await check_sent_applications(db)
    return {"checked": checked, "sent": sent}


@router.post("/{app_id}/check-sent")
async def check_sent_one(app_id: int, db: AsyncSession = Depends(get_db)):
    if await ApplicationRepository(db).get_by_id(app_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    checked = len(await get_candidates(db, app_id))
    sent = await check_sent_applications(db, app_id=app_id)
    return {"checked": checked, "sent": sent}


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


@router.post("/{app_id}/cover-letter", status_code=status.HTTP_202_ACCEPTED)
async def generate_cover_letter(
    app_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    repo = ApplicationRepository(db)
    record = await repo.get_by_id(app_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    if record.status not in ("ready", "applied", "interview", "offer"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La candidatura deve avere un'analisi completata prima di generare la lettera.",
        )
    if record.cover_letter_status == "generating":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Generazione lettera già in corso.")

    cv_repo = CVRepository(db)
    cv = await cv_repo.get_by_id(record.cv_id)
    if cv is None or not cv.parsed_data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV non parsato.")

    await repo.set_cover_letter_status(app_id, "generating")
    cv_parsed_data = json.loads(cv.parsed_data)
    optimization_data = json.loads(record.optimization_data) if record.optimization_data else None

    background_tasks.add_task(
        _run_cover_letter,
        app_id,
        cv_parsed_data,
        record.company,
        record.role,
        record.job_description,
        optimization_data,
    )

    return {
        "application_id": app_id,
        "cover_letter_status": "generating",
        "message": "Generazione lettera avviata. Usa GET /applications/{id} per monitorare lo stato.",
    }


@router.patch("/{app_id}", response_model=JobApplicationResponse)
async def update_meta(app_id: int, body: JobApplicationUpdate, db: AsyncSession = Depends(get_db)):
    repo = ApplicationRepository(db)
    current = await repo.get_by_id(app_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    sent = body.model_fields_set
    advertiser_type = body.advertiser_type if "advertiser_type" in sent else current.advertiser_type
    contact_email = body.contact_email if "contact_email" in sent else current.contact_email
    return await repo.set_meta(app_id, advertiser_type, contact_email)


@router.post("/{app_id}/draft", status_code=status.HTTP_202_ACCEPTED)
async def create_tailored_draft(
    app_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    repo = ApplicationRepository(db)
    record = await repo.get_by_id(app_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    if record.draft_status == "generating":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bozza già in generazione.")
    cv = await CVRepository(db).get_by_id(record.cv_id)
    if cv is None or not cv.parsed_data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV non parsato.")

    await repo.set_draft_status(app_id, "generating")
    background_tasks.add_task(run_application_draft, app_id)
    return {"application_id": app_id, "draft_status": "generating"}


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
    documents = await repo.list_documents(app_id)
    return _build_detail(record, documents)


@router.get("/{app_id}/documents", response_model=list[DocumentMeta])
async def list_documents(app_id: int, db: AsyncSession = Depends(get_db)):
    repo = ApplicationRepository(db)
    if await repo.get_by_id(app_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    return await repo.list_documents(app_id)


@router.get("/{app_id}/documents/{doc_id}")
async def download_document(app_id: int, doc_id: int, db: AsyncSession = Depends(get_db)):
    repo = ApplicationRepository(db)
    doc = await repo.get_document(app_id, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento non trovato.")
    safe = "".join(c if c.isascii() and c.isprintable() and c not in ('"', "\\") else "_" for c in doc.filename)
    return Response(
        content=doc.content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe}"'},
    )
