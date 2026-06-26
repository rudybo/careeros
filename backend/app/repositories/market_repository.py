import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.market import JobOpportunity, UserPreferences


class PreferencesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> UserPreferences | None:
        result = await self._session.execute(select(UserPreferences).limit(1))
        return result.scalar_one_or_none()

    async def upsert(self, data: dict) -> UserPreferences:
        prefs = await self.get()
        if prefs is None:
            prefs = UserPreferences()
            self._session.add(prefs)
        for key, value in data.items():
            if key in ("sectors", "target_roles"):
                setattr(prefs, key, json.dumps(value, ensure_ascii=False) if value is not None else None)
            else:
                setattr(prefs, key, value)
        await self._session.commit()
        await self._session.refresh(prefs)
        return prefs


class OpportunityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, records: list[dict]) -> tuple[int, int]:
        created, skipped = 0, 0
        for rec in records:
            existing = await self._session.execute(
                select(JobOpportunity).where(JobOpportunity.external_id == rec["external_id"])
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            opp = JobOpportunity(**rec)
            self._session.add(opp)
            created += 1
        await self._session.commit()
        return created, skipped

    async def get_all(self, status: str | None = None, limit: int | None = None) -> list[JobOpportunity]:
        q = select(JobOpportunity).order_by(JobOpportunity.match_score.desc().nullslast(), JobOpportunity.found_at.desc())
        if status:
            q = q.where(JobOpportunity.status == status)
        if limit:
            q = q.limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def update_status(self, opp_id: int, status: str) -> JobOpportunity | None:
        result = await self._session.execute(select(JobOpportunity).where(JobOpportunity.id == opp_id))
        opp = result.scalar_one_or_none()
        if opp is None:
            return None
        opp.status = status
        await self._session.commit()
        await self._session.refresh(opp)
        return opp

    async def get_by_id(self, opp_id: int) -> JobOpportunity | None:
        result = await self._session.execute(select(JobOpportunity).where(JobOpportunity.id == opp_id))
        return result.scalar_one_or_none()

    async def get_unnotified_above(self, min_score: int) -> list[JobOpportunity]:
        """Offerte 'new' mai notificate con match_score >= soglia (per Telegram)."""
        result = await self._session.execute(
            select(JobOpportunity)
            .where(
                JobOpportunity.notified.is_(False),
                JobOpportunity.status == "new",
                JobOpportunity.match_score >= min_score,
            )
            .order_by(JobOpportunity.match_score.desc())
        )
        return list(result.scalars().all())

    async def mark_notified(self, opp_id: int) -> None:
        opp = await self.get_by_id(opp_id)
        if opp:
            opp.notified = True
            await self._session.commit()

    async def update_draft_status(self, opp_id: int, status: str) -> JobOpportunity | None:
        result = await self._session.execute(select(JobOpportunity).where(JobOpportunity.id == opp_id))
        opp = result.scalar_one_or_none()
        if opp is None:
            return None
        opp.draft_status = status
        await self._session.commit()
        await self._session.refresh(opp)
        return opp

    async def update_draft(self, opp_id: int, draft_id: str, gmail_url: str) -> JobOpportunity | None:
        result = await self._session.execute(select(JobOpportunity).where(JobOpportunity.id == opp_id))
        opp = result.scalar_one_or_none()
        if opp is None:
            return None
        opp.draft_id = draft_id
        opp.gmail_url = gmail_url
        opp.draft_status = "ready"
        await self._session.commit()
        await self._session.refresh(opp)
        return opp
