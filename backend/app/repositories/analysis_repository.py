import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import CareerAnalysis


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, cv_id: int) -> CareerAnalysis:
        analysis = CareerAnalysis(cv_id=cv_id, status="pending")
        self._session.add(analysis)
        await self._session.commit()
        await self._session.refresh(analysis)
        return analysis

    async def update_analysis_data(self, analysis_id: int, data: dict) -> CareerAnalysis | None:
        analysis = await self.get_by_id(analysis_id)
        if analysis is None:
            return None
        analysis.analysis_data = json.dumps(data, ensure_ascii=False)
        analysis.status = "completed"
        await self._session.commit()
        await self._session.refresh(analysis)
        return analysis

    async def update_status(self, analysis_id: int, status: str) -> None:
        analysis = await self.get_by_id(analysis_id)
        if analysis:
            analysis.status = status
            await self._session.commit()

    async def get_by_id(self, analysis_id: int) -> CareerAnalysis | None:
        result = await self._session.execute(
            select(CareerAnalysis).where(CareerAnalysis.id == analysis_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_by_cv(self, cv_id: int) -> CareerAnalysis | None:
        result = await self._session.execute(
            select(CareerAnalysis)
            .where(CareerAnalysis.cv_id == cv_id)
            .order_by(CareerAnalysis.created_at.desc())
        )
        return result.scalars().first()

    async def get_all_by_cv(self, cv_id: int) -> list[CareerAnalysis]:
        result = await self._session.execute(
            select(CareerAnalysis)
            .where(CareerAnalysis.cv_id == cv_id)
            .order_by(CareerAnalysis.created_at.desc())
        )
        return list(result.scalars().all())
