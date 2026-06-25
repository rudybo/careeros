from datetime import datetime
from pydantic import BaseModel


class UserPreferencesUpdate(BaseModel):
    ral_min: int | None = None
    ral_max: int | None = None
    city: str | None = None
    radius_km: int | None = None
    work_mode: str | None = None        # remote / hybrid / onsite
    sectors: list[str] | None = None
    target_roles: list[str] | None = None
    contract_type: str | None = None    # indeterminato / determinato / piva
    company_size: str | None = None     # startup / sme / enterprise
    language: str | None = None         # italian / english / bilingual
    available_travel: bool | None = None


class UserPreferencesResponse(UserPreferencesUpdate):
    id: int
    updated_at: datetime
    model_config = {"from_attributes": True}


class JobOpportunityResponse(BaseModel):
    id: int
    external_id: str
    source: str
    title: str
    company: str | None
    location: str | None
    url: str
    salary_min: float | None
    salary_max: float | None
    work_mode: str | None
    match_score: int | None
    match_reasons: list[str] | None
    status: str
    draft_status: str
    gmail_url: str | None
    found_at: datetime
    model_config = {"from_attributes": True}


class OpportunityStatusUpdate(BaseModel):
    status: str   # new / saved / dismissed
