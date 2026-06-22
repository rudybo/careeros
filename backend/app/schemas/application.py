from datetime import datetime

from pydantic import BaseModel, Field


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


class JobApplicationCreate(BaseModel):
    cv_id: int
    company: str
    role: str
    job_description: str


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


class JobApplicationDetailResponse(BaseModel):
    id: int
    cv_id: int
    company: str
    role: str
    job_description: str
    status: str
    optimization: CVOptimization | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
