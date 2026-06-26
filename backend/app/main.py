import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router
from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def _reset_stuck_drafts() -> None:
    """Reset any 'generating' draft statuses left over from a previous crashed run."""
    from sqlalchemy import update
    from app.models.market import JobOpportunity
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(JobOpportunity)
            .where(JobOpportunity.draft_status == "generating")
            .values(draft_status="none")
        )
        await session.commit()


async def _scheduled_market_search() -> None:
    """Run Hermes market search automatically (called by scheduler)."""
    import json
    from app.agents.market_scout import agent as scout
    from app.repositories.cv_repository import CVRepository
    from app.repositories.market_repository import OpportunityRepository, PreferencesRepository
    from app.schemas.cv import ParsedCV
    async with AsyncSessionLocal() as session:
        cv_repo = CVRepository(session)
        cvs = await cv_repo.get_all()
        parsed = next((c for c in cvs if c.status == "parsed" and c.parsed_data), None)
        if not parsed:
            logger.warning("Hermes scheduler: nessun CV parsato trovato, skip.")
            return
        prefs_repo = PreferencesRepository(session)
        opp_repo = OpportunityRepository(session)
        try:
            cv = ParsedCV(**json.loads(parsed.parsed_data))
            prefs = await prefs_repo.get()
            results = await scout.search(cv, prefs)
            created, skipped = await opp_repo.upsert_many(results)
            logger.info("Hermes scheduler: %d nuove offerte, %d già presenti", created, skipped)
        except Exception as e:
            logger.error("Hermes scheduler errore: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _reset_stuck_drafts()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_scheduled_market_search, "cron", hour=8,  minute=0, id="iris_morning")
    scheduler.add_job(_scheduled_market_search, "cron", hour=19, minute=0, id="iris_evening")
    scheduler.start()
    logger.info("Iris scheduler avviata: 08:00 e 19:00")

    import asyncio
    from app.services import telegram_service
    telegram_task = asyncio.create_task(telegram_service.poll_loop())

    yield

    telegram_task.cancel()
    scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered career platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
