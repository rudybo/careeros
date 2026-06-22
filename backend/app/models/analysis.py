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
