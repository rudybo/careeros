import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.repositories.application_repository import ApplicationRepository
from app.repositories.cv_repository import BASE_BLOCK_MSG, CV_KINDS, CVRepository
from app.schemas.cv import CVDetailResponse, CVPatch, CVUploadResponse, ParsedCV
from app.services.cv_extractor import CVExtractionError, UnsupportedFileTypeError, extract_text
from app.services.ollama_service import OllamaParsingError, OllamaUnavailableError, parse_cv_with_ollama

logger = logging.getLogger(__name__)

_MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _safe_filename(name: str) -> str:
    name = re.sub(r'["\\\r\n]', "", name)
    return re.sub(r"[^\x20-\x7e]", "_", name) or "cv"

router = APIRouter(prefix="/cv", tags=["CV"])


async def _run_parsing(cv_id: int, raw_text: str) -> None:
    """Background task: estrae i dati dal CV e, a parsing riuscito, avvia
    AUTOMATICAMENTE l'analisi di carriera (caricare un CV = chiedere l'analisi)."""
    async with AsyncSessionLocal() as session:
        repo = CVRepository(session)
        try:
            parsed_dict = await parse_cv_with_ollama(raw_text)
            await repo.update_parsed_data(cv_id, parsed_dict)
            logger.info("Parsing completato: cv_id=%d", cv_id)
        except (OllamaUnavailableError, OllamaParsingError) as e:
            await repo.update_status(cv_id, "error")
            logger.error("Parsing fallito: cv_id=%d error=%s", cv_id, e)
            return

    await _auto_analyze(cv_id, parsed_dict)


async def _auto_analyze(cv_id: int, parsed_dict: dict) -> None:
    """Crea ed esegue subito un'analisi di carriera per il CV appena parsato."""
    # Import locale per evitare problemi di ordine di caricamento dei moduli
    from app.api.v1.endpoints.analysis import _run_analysis
    from app.repositories.analysis_repository import AnalysisRepository

    async with AsyncSessionLocal() as session:
        arepo = AnalysisRepository(session)
        record = await arepo.create(cv_id=cv_id)
        await arepo.update_status(record.id, "analyzing")
        analysis_id = record.id

    logger.info("Auto-analisi avviata: cv_id=%d analysis_id=%d", cv_id, analysis_id)
    await _run_analysis(analysis_id, cv_id, parsed_dict)


def _build_detail_response(cv) -> CVDetailResponse:
    parsed_data = ParsedCV(**json.loads(cv.parsed_data)) if cv.parsed_data else None
    return CVDetailResponse(
        id=cv.id,
        filename=cv.filename,
        status=cv.status,
        parsed_data=parsed_data,
        created_at=cv.created_at,
        updated_at=cv.updated_at,
        kind=cv.kind,
        is_base=cv.is_base,
        archived=cv.archived,
        has_file=cv.has_file,
    )


@router.post("/upload", response_model=CVUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(file: UploadFile, kind: str = Form("altro"), db: AsyncSession = Depends(get_db)):
    if kind not in CV_KINDS:
        raise HTTPException(status_code=422, detail=f"Tipo non valido. Valori: {list(CV_KINDS)}")
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
    cv = await repo.create(
        filename=file.filename,
        raw_text=raw_text,
        file_content=content,
        file_mime=_MIME_BY_EXT.get(Path(file.filename).suffix.lower()),
    )
    if kind != "altro":
        cv = await repo.set_kind(cv.id, kind)

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


@router.get("/{cv_id}/file")
async def get_cv_file(cv_id: int, db: AsyncSession = Depends(get_db)):
    found = await CVRepository(db).get_file(cv_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File originale non disponibile.")
    filename, mime, data = found
    disposition = "inline" if mime == "application/pdf" else "attachment"
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'{disposition}; filename="{_safe_filename(filename)}"'},
    )


@router.get("/{cv_id}", response_model=CVDetailResponse)
async def get_cv(cv_id: int, db: AsyncSession = Depends(get_db)):
    repo = CVRepository(db)
    cv = await repo.get_by_id(cv_id)

    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trovato.")

    return _build_detail_response(cv)


@router.delete("/{cv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(cv_id: int, db: AsyncSession = Depends(get_db)):
    repo = CVRepository(db)
    cv = await repo.get_by_id(cv_id)
    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trovato.")
    if cv.is_base:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=BASE_BLOCK_MSG)
    # Cascade: remove linked applications first
    app_repo = ApplicationRepository(db)
    n = await app_repo.delete_by_cv_id(cv_id)
    if n:
        logger.info("Cascade delete: %d candidature eliminate per cv_id=%d", n, cv_id)
    await repo.delete(cv_id)
    logger.info("CV eliminato: id=%d", cv_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/", response_model=list[CVUploadResponse])
async def list_cvs(archived: bool | None = None, db: AsyncSession = Depends(get_db)):
    repo = CVRepository(db)
    cvs = await repo.get_all()
    if archived is None:
        return cvs
    return [c for c in cvs if c.archived == archived]


@router.patch("/{cv_id}", response_model=CVUploadResponse)
async def patch_cv(cv_id: int, body: CVPatch, db: AsyncSession = Depends(get_db)):
    repo = CVRepository(db)
    cv = await repo.get_by_id(cv_id)
    if cv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV non trovato.")
    fields = body.model_fields_set
    if "kind" in fields and body.kind is not None and body.kind not in CV_KINDS:
        raise HTTPException(status_code=422, detail=f"Tipo non valido. Valori: {list(CV_KINDS)}")
    try:
        if "kind" in fields and body.kind is not None:
            cv = await repo.set_kind(cv_id, body.kind)
        if "is_base" in fields and body.is_base is not None:
            if body.is_base:
                cv = await repo.set_base(cv_id)
            elif cv.is_base:
                raise ValueError(BASE_BLOCK_MSG)
        if "archived" in fields and body.archived is not None:
            cv = await (repo.archive(cv_id) if body.archived else repo.unarchive(cv_id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return cv
