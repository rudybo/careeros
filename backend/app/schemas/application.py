from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.cv import ParsedCV


class SectionSuggestion(BaseModel):
    section: str   # summary / skills / experience / education
    issue: str
    suggestion: str


class CVOptimization(BaseModel):
    match_score: int = Field(ge=0, le=100)
    matched_keywords: list[str]
    missing_keywords: list[str]
    ats_warnings: list[str]
    section_suggestions: list[SectionSuggestion]
    cover_letter_hints: list[str]
    optimized_summary: str


AdvertiserType = Literal["recruiter", "direct"]


class JobApplicationCreate(BaseModel):
    cv_id: int
    company: str | None = None
    role: str | None = None
    job_description: str | None = None
    source_url: str | None = None
    advertiser_type: AdvertiserType | None = None
    contact_email: str | None = None

    @model_validator(mode="after")
    def _need_text_or_url(self):
        if not (self.job_description and self.job_description.strip()) and not (
            self.source_url and self.source_url.strip()
        ):
            raise ValueError("Serve il testo dell'annuncio oppure il link.")
        return self


class JobApplicationUpdate(BaseModel):
    advertiser_type: AdvertiserType | None = None
    contact_email: str | None = None


class JobApplicationStatusUpdate(BaseModel):
    status: str  # draft / ready / applied / interview / offer / rejected


class JobApplicationResponse(BaseModel):
    id: int
    cv_id: int
    company: str
    role: str
    status: str
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CoverLetter(BaseModel):
    subject: str
    full_text: str


class StatusEvent(BaseModel):
    status: str
    at: datetime


class JobApplicationDetailResponse(BaseModel):
    id: int
    cv_id: int
    company: str
    role: str
    job_description: str
    status: str
    status_history: list[StatusEvent] = []
    optimization: CVOptimization | None
    cover_letter: CoverLetter | None
    cover_letter_status: str
    source_url: str | None = None
    advertiser_type: AdvertiserType | None = None
    contact_email: str | None = None
    tailored_cv: ParsedCV | None = None
    draft_url: str | None = None
    draft_status: str = "idle"
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
