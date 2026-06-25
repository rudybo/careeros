from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ral_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ral_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    radius_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)   # remote/hybrid/onsite
    sectors: Mapped[str | None] = mapped_column(Text, nullable=True)            # JSON array
    target_roles: Mapped[str | None] = mapped_column(Text, nullable=True)      # JSON array
    contract_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True) # startup/sme/enterprise
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    available_travel: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class JobOpportunity(Base):
    __tablename__ = "job_opportunities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(50), default="adzuna")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)      # JSON array
    status: Mapped[str] = mapped_column(String(50), default="new")              # new/saved/dismissed
    draft_status: Mapped[str] = mapped_column(String(50), default="none")      # none/ready/sent
    draft_id: Mapped[str | None] = mapped_column(String(255), nullable=True)   # Gmail draft ID
    gmail_url: Mapped[str | None] = mapped_column(Text, nullable=True)         # direct link to draft
    found_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
