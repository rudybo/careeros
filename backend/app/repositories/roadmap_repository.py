import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import RoadmapItem


def _fingerprint(action: str) -> str:
    """Normalizza un'azione per riconoscere duplicati anche se riformulati:
    minuscolo, senza punteggiatura, spazi compattati, primi 50 caratteri."""
    norm = re.sub(r"[^\w\s]", "", (action or "").lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm[:50]


class RoadmapRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_cv(self, cv_id: int) -> list[RoadmapItem]:
        result = await self._session.execute(
            select(RoadmapItem)
            .where(RoadmapItem.cv_id == cv_id)
            .order_by(RoadmapItem.created_at.asc())
        )
        return list(result.scalars().all())

    async def set_status(self, item_id: int, status: str) -> RoadmapItem | None:
        item = await self._session.get(RoadmapItem, item_id)
        if item is None:
            return None
        item.status = status
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def merge_steps(self, cv_id: int, steps: list[dict]) -> int:
        """Aggiunge come 'todo' solo gli step non già presenti (per fingerprint),
        in qualsiasi stato. Quelli completati/annullati restano e non vengono
        riproposti. Ritorna il numero di nuovi item aggiunti."""
        existing = await self.get_by_cv(cv_id)
        seen = {it.fingerprint for it in existing}
        added = 0
        for step in steps:
            action = step.get("action", "").strip()
            if not action:
                continue
            fp = _fingerprint(action)
            if fp in seen:
                continue
            seen.add(fp)
            self._session.add(RoadmapItem(
                cv_id=cv_id,
                action=action,
                category=step.get("category", "skill"),
                impact=step.get("impact"),
                timeframe=step.get("timeframe"),
                status="todo",
                fingerprint=fp,
            ))
            added += 1
        if added:
            await self._session.commit()
        return added

    async def get_done_and_dismissed(self, cv_id: int) -> tuple[list[str], list[str]]:
        """Ritorna (azioni completate, azioni annullate) per informare il modello."""
        items = await self.get_by_cv(cv_id)
        done = [it.action for it in items if it.status == "done"]
        dismissed = [it.action for it in items if it.status == "dismissed"]
        return done, dismissed
