from datetime import datetime

from pydantic import BaseModel, Field


class TargetRole(BaseModel):
    title: str
    match_percentage: int = Field(ge=0, le=100)
    reason: str
    market_demand: str  # alto / medio / basso


class SkillGap(BaseModel):
    skill: str
    priority: str  # alta / media / bassa
    why_needed: str
    how_to_acquire: str
    estimated_time: str


class RoadmapStep(BaseModel):
    order: int
    action: str
    category: str  # skill / certificazione / network / portfolio
    impact: str
    timeframe: str


class CareerAnalysis(BaseModel):
    executive_summary: str
    target_roles: list[TargetRole]
    skill_gaps: list[SkillGap]
    roadmap: list[RoadmapStep]


class CareerAnalysisResponse(BaseModel):
    id: int
    cv_id: int
    status: str
    analysis: CareerAnalysis | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
