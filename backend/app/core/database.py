from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def _migrate_add_columns(conn) -> None:
    """Add new columns to existing tables without dropping data."""
    def _add_if_missing(sync_conn, table: str, column: str, definition: str) -> None:
        cols = [c["name"] for c in inspect(sync_conn).get_columns(table)]
        if column not in cols:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

    await conn.run_sync(_add_if_missing, "job_applications", "cover_letter", "TEXT")
    await conn.run_sync(_add_if_missing, "job_applications", "cover_letter_status", "VARCHAR(50) DEFAULT 'idle'")
    await conn.run_sync(_add_if_missing, "job_opportunities", "draft_status", "VARCHAR(50) DEFAULT 'none'")
    await conn.run_sync(_add_if_missing, "job_opportunities", "draft_id", "VARCHAR(255)")
    await conn.run_sync(_add_if_missing, "job_opportunities", "gmail_url", "TEXT")
    await conn.run_sync(_add_if_missing, "user_preferences", "target_roles", "TEXT")


async def init_db() -> None:
    # Import all models so SQLAlchemy registers them before create_all
    import app.models.analysis  # noqa: F401
    import app.models.application  # noqa: F401
    import app.models.cv  # noqa: F401
    import app.models.market  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add columns introduced after initial schema (SQLite-compatible migration)
        await _migrate_add_columns(conn)
