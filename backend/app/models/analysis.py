from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CareerAnalysis(Base):
    __tablename__ = "career_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cv_id: Mapped[int] = mapped_column(Integer, ForeignKey("cvs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    analysis_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RoadmapItem(Base):
    """Checklist persistente per CV: le attività della roadmap che l'utente
    può segnare come completate o annullare. Sopravvive ai ricalcoli."""
    __tablename__ = "roadmap_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cv_id: Mapped[int] = mapped_column(Integer, ForeignKey("cvs.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="skill")
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo / done / dismissed
    fingerprint: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AtsKeywordItem(Base):
    """Checklist persistente per CV delle keyword ATS suggerite. L'utente le segna
    'added' (aggiunta al CV) o 'ignored' (ce l'ho già / non rilevante); al ricalcolo
    non vengono riproposte."""
    __tablename__ = "ats_keyword_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cv_id: Mapped[int] = mapped_column(Integer, ForeignKey("cvs.id"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo / added / ignored
    fingerprint: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
