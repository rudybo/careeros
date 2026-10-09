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
    await conn.run_sync(_add_if_missing, "job_applications", "source_url", "TEXT")
    await conn.run_sync(_add_if_missing, "job_applications", "advertiser_type", "VARCHAR(20)")
    await conn.run_sync(_add_if_missing, "job_applications", "contact_email", "VARCHAR(255)")
    await conn.run_sync(_add_if_missing, "job_applications", "tailored_cv", "TEXT")
    await conn.run_sync(_add_if_missing, "job_applications", "draft_url", "TEXT")
    await conn.run_sync(_add_if_missing, "job_applications", "draft_status", "VARCHAR(50) DEFAULT 'idle'")
    await conn.run_sync(_add_if_missing, "job_applications", "opportunity_id", "INTEGER")
    await conn.run_sync(_add_if_missing, "job_applications", "gmail_thread_id", "VARCHAR(255)")
    await conn.run_sync(_add_if_missing, "job_applications", "sent_at", "DATETIME")
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_applications_opportunity_id ON job_applications (opportunity_id)"))
    await conn.run_sync(_add_if_missing, "job_opportunities", "draft_status", "VARCHAR(50) DEFAULT 'none'")
    await conn.run_sync(_add_if_missing, "job_opportunities", "draft_id", "VARCHAR(255)")
    await conn.run_sync(_add_if_missing, "job_opportunities", "gmail_url", "TEXT")
    await conn.run_sync(_add_if_missing, "job_opportunities", "advertiser_type", "VARCHAR(20)")
    await conn.run_sync(_add_if_missing, "user_preferences", "target_roles", "TEXT")
    await conn.run_sync(_add_if_missing, "cvs", "kind", "VARCHAR(20) DEFAULT 'altro'")
    await conn.run_sync(_add_if_missing, "cvs", "is_base", "BOOLEAN DEFAULT 0")
    await conn.run_sync(_add_if_missing, "cvs", "archived", "BOOLEAN DEFAULT 0")
    # DEFAULT 1: le offerte esistenti (pre-feature) risultano già notificate, niente flood.
    # Le nuove offerte inserite dall'ORM usano il default del modello (False) → verranno notificate.
    await conn.run_sync(_add_if_missing, "job_opportunities", "notified", "BOOLEAN DEFAULT 1")


async def _migrate_base_cv(conn) -> None:
    """Se nessun CV e' base, marca base il CV parsato non archiviato con id minore (idempotente)."""
    has_base = (await conn.execute(text("SELECT 1 FROM cvs WHERE is_base = 1 LIMIT 1"))).first()
    if has_base:
        return
    row = (await conn.execute(text(
        "SELECT id FROM cvs WHERE status = 'parsed' AND archived = 0 ORDER BY id LIMIT 1"
    ))).first()
    if row:
        await conn.execute(text("UPDATE cvs SET is_base = 1 WHERE id = :i"), {"i": row[0]})


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
        await _migrate_base_cv(conn)
