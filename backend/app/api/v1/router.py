from fastapi import APIRouter

from app.api.v1.endpoints import analysis, application, cv, market, system
from app.core.config import settings

router = APIRouter(prefix="/api/v1")
router.include_router(cv.router)
router.include_router(analysis.router)
router.include_router(application.router)
router.include_router(market.router)
router.include_router(system.router)


@router.get("/info")
async def info():
    """Provider LLM e modello attualmente in uso, per la UI."""
    provider = settings.llm_provider.lower()
    model = settings.groq_model if provider == "groq" else settings.ollama_model
    return {"provider": provider, "model": model, "version": settings.app_version}
