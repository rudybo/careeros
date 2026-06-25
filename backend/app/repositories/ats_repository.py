from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AtsKeywordItem
from app.repositories.roadmap_repository import _fingerprint


class AtsKeywordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_cv(self, cv_id: int) -> list[AtsKeywordItem]:
        result = await self._session.execute(
            select(AtsKeywordItem)
            .where(AtsKeywordItem.cv_id == cv_id)
            .order_by(AtsKeywordItem.created_at.asc())
        )
        return list(result.scalars().all())

    async def set_status(self, item_id: int, status: str) -> AtsKeywordItem | None:
        item = await self._session.get(AtsKeywordItem, item_id)
        if item is None:
            return None
        item.status = status
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def merge_keywords(self, cv_id: int, keywords: list[dict]) -> int:
        """Aggiunge come 'todo' solo le keyword non già presenti (per fingerprint),
        in qualsiasi stato. Quelle aggiunte/ignorate restano e non tornano.
        Ritorna il numero di nuove keyword aggiunte."""
        existing = await self.get_by_cv(cv_id)
        seen = {it.fingerprint for it in existing}
        added = 0
        for kw in keywords:
            keyword = (kw.get("keyword") or "").strip()
            if not keyword:
                continue
            fp = _fingerprint(keyword)
            if fp in seen:
                continue
            seen.add(fp)
            self._session.add(AtsKeywordItem(
                cv_id=cv_id,
                keyword=keyword,
                reason=kw.get("reason"),
                status="todo",
                fingerprint=fp,
            ))
            added += 1
        if added:
            await self._session.commit()
        return added

    async def get_handled(self, cv_id: int) -> list[str]:
        """Keyword aggiunte/ignorate/segnate come gap — da non riproporre."""
        items = await self.get_by_cv(cv_id)
        return [it.keyword for it in items if it.status in ("added", "ignored", "gap")]
