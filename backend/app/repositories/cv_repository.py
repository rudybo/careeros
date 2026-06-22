import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cv import CV


class CVRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, filename: str, raw_text: str) -> CV:
        cv = CV(filename=filename, raw_text=raw_text, status="uploaded")
        self._session.add(cv)
        await self._session.commit()
        await self._session.refresh(cv)
        return cv

    async def update_parsed_data(self, cv_id: int, parsed_data: dict) -> CV | None:
        cv = await self.get_by_id(cv_id)
        if cv is None:
            return None
        cv.parsed_data = json.dumps(parsed_data)
        cv.status = "parsed"
        await self._session.commit()
        await self._session.refresh(cv)
        return cv

    async def update_status(self, cv_id: int, status: str) -> None:
        cv = await self.get_by_id(cv_id)
        if cv:
            cv.status = status
            await self._session.commit()

    async def get_by_id(self, cv_id: int) -> CV | None:
        result = await self._session.execute(select(CV).where(CV.id == cv_id))
        return result.scalar_one_or_none()

    async def get_all(self) -> list[CV]:
        result = await self._session.execute(select(CV).order_by(CV.created_at.desc()))
        return list(result.scalars().all())
