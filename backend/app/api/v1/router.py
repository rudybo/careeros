from fastapi import APIRouter

from app.api.v1.endpoints import analysis, application, cv

router = APIRouter(prefix="/api/v1")
router.include_router(cv.router)
router.include_router(analysis.router)
router.include_router(application.router)
