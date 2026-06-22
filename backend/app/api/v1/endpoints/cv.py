import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.repositories.cv_repository import CVRepository
from app.schemas.cv import CVDetailResponse, CVUploadResponse, ParsedCV
from app.services.cv_extractor import CVExtractionError, UnsupportedFileTypeError, extract_text
from app.services.ollama_service import OllamaParsingError, OllamaUnavailableError, parse_cv_with_ollama

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cv", tags=["CV"])


async def _run_parsing(cv_id: int, raw_text: str) -> None:
    """Background task: calls Ollama and persists result with its own DB session."""
    async with AsyncSessionLocal() as session:
        repo = CVRepository(session)
        try:
            parsed_dict = await parse_cv_with_ollama(raw_text)
            await repo.update_parsed_data(cv_id, parsed_dict)
            logger.info("Parsing completato: cv_id=%d", cv_id)
        except (OllamaUnavailableError, OllamaParsingError) as e:
            await repo.update_status(cv_id, "error")
            logger.error("Parsing fallito: cv_id=%d error=%s", cv_id, e)


def _build_detail_response(cv) -> CVDetailResponse:
    parsed_data = ParsedCV(**json.loads(cv.parsed_data)) if cv.parsed_data else None
    return CVDetailResponse(
        id=cv.id,
        filename=cv.filename,
        status=cv.status,
        parsed_data=parsed_data,
        created_at=cv.created_at,
        updated_at=cv.updated_at,
    )


@router.post("/upload", response_model=CVUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(file: UploadFile, db: AsyncSession = Depends(get_db)):
    content = await file.read()

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File troppo grande. Massimo {settings.max_upload_size_mb}MB.",
        )

    try:
        raw_text = extract_text(file.filename, content)
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(e))
    except CVExtractionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    repo = CVRepository(db)
    cv = await repo.create(filename=file.filename, raw_text=raw_text)

    logger.info("CV caricato: id=%d filename=%s", cv.id, cv.filename)
    return cv


@router.post("/{cv_id}/parse", status_code=status.HTTP_202_ACCEPTED)
async def parse_cv(cv_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    repo = CVRepository(db)
    cv = await repo.get_by_id(cv_id)

    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trovato.")

    if cv.status == "parsing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parsing già in corso.")

    await repo.update_status(cv_id, "parsing")
    background_tasks.add_task(_run_parsing, cv_id, cv.raw_text)

    logger.info("Parsing avviato in background: cv_id=%d", cv_id)
    return {"cv_id": cv_id, "status": "parsing", "message": "Parsing avviato. Usa GET /cv/{id} per monitorare lo stato."}


@router.get("/{cv_id}", response_model=CVDetailResponse)
async def get_cv(cv_id: int, db: AsyncSession = Depends(get_db)):
    repo = CVRepository(db)
    cv = await repo.get_by_id(cv_id)

    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trovato.")

    return _build_detail_response(cv)


@router.get("/", response_model=list[CVUploadResponse])
async def list_cvs(db: AsyncSession = Depends(get_db)):
    repo = CVRepository(db)
    return await repo.get_all()
