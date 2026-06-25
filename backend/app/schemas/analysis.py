from datetime import datetime

from pydantic import BaseModel, Field


class TargetRole(BaseModel):
    title: str
    match_percentage: int = Field(ge=0, le=100)
    reason: str
    market_demand: str  # alto / medio / basso


class Resource(BaseModel):
    title: str          # nome del corso/certificazione
    provider: str       # es. Microsoft Learn, Coursera, Google Cloud Skills Boost
    cost: str           # "gratuito" / "a pagamento"


class SkillGap(BaseModel):
    skill: str
    priority: str  # alta / media / bassa
    why_needed: str
    how_to_acquire: str
    estimated_time: str
    resources: list[Resource] = Field(default_factory=list)


class RoadmapStep(BaseModel):
    order: int
    action: str
    category: str  # skill / certificazione / network / portfolio
    impact: str
    timeframe: str


class AtsKeyword(BaseModel):
    keyword: str
    reason: str         # perché serve / dove inserirla nel CV


class CareerAnalysis(BaseModel):
    executive_summary: str
    target_roles: list[TargetRole]
    skill_gaps: list[SkillGap]
    roadmap: list[RoadmapStep]
    ats_keywords: list[AtsKeyword] = Field(default_factory=list)


class CareerAnalysisResponse(BaseModel):
    id: int
    cv_id: int
    status: str
    analysis: CareerAnalysis | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoadmapItemResponse(BaseModel):
    id: int
    cv_id: int
    action: str
    category: str
    impact: str | None
    timeframe: str | None
    status: str  # todo / done / dismissed
    created_at: datetime

    model_config = {"from_attributes": True}


class RoadmapItemUpdate(BaseModel):
    status: str  # todo / done / dismissed


class AtsKeywordItemResponse(BaseModel):
    id: int
    cv_id: int
    keyword: str
    reason: str | None
    status: str  # todo / added / ignored / gap
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AtsKeywordItemUpdate(BaseModel):
    status: str  # todo / added / ignored / gap
