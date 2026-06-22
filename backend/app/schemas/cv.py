from datetime import datetime

from pydantic import BaseModel, Field


class WorkExperience(BaseModel):
    company: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class Education(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    year: str | None = None


class ParsedCV(BaseModel):
    full_name: str = Field(description="Nome e cognome del candidato")
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = Field(None, description="Sommario professionale o obiettivo")
    skills: list[str] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class CVUploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CVDetailResponse(BaseModel):
    id: int
    filename: str
    status: str
    parsed_data: ParsedCV | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
