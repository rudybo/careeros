import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import JobApplication


class ApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, cv_id: int, company: str, role: str, job_description: str) -> JobApplication:
        app = JobApplication(
            cv_id=cv_id,
            company=company,
            role=role,
            job_description=job_description,
            status="draft",
        )
        self._session.add(app)
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def update_status(self, app_id: int, status: str) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        now = datetime.now(timezone.utc)
        app.status = status
        if status == "applied":
            app.applied_at = now
        # Cronologia: registra la data di ogni cambio di stato
        hist = json.loads(app.status_history) if app.status_history else []
        hist.append({"status": status, "at": now.isoformat()})
        app.status_history = json.dumps(hist, ensure_ascii=False)
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def delete_by_cv_id(self, cv_id: int) -> int:
        result = await self._session.execute(
            select(JobApplication).where(JobApplication.cv_id == cv_id)
        )
        apps = list(result.scalars().all())
        for app in apps:
            await self._session.delete(app)
        await self._session.commit()
        return len(apps)

    async def update_cover_letter(self, app_id: int, data: dict) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        app.cover_letter = json.dumps(data, ensure_ascii=False)
        app.cover_letter_status = "ready"
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def set_cover_letter_status(self, app_id: int, status: str) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        app.cover_letter_status = status
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def update_optimization(self, app_id: int, data: dict) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        app.optimization_data = json.dumps(data, ensure_ascii=False)
        app.status = "ready"
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def get_by_id(self, app_id: int) -> JobApplication | None:
        result = await self._session.execute(
            select(JobApplication).where(JobApplication.id == app_id)
        )
        return result.scalar_one_or_none()

    async def get_all_by_cv(self, cv_id: int) -> list[JobApplication]:
        result = await self._session.execute(
            select(JobApplication)
            .where(JobApplication.cv_id == cv_id)
            .order_by(JobApplication.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_all(self) -> list[JobApplication]:
        result = await self._session.execute(
            select(JobApplication).order_by(JobApplication.created_at.desc())
        )
        return list(result.scalars().all())
