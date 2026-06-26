import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AtsKeywordItem
from app.repositories.roadmap_repository import _fingerprint


def _present(keyword: str, text: str) -> bool:
    """True se la keyword compare nel testo (confine di parola, case-insensitive)."""
    if not keyword or not text:
        return False
    return re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text.lower()) is not None


class AtsKeywordRepository:
    """Lista keyword ATS a livello di CARRIERA (unica, non per singolo CV).
    Il cv_id sui record indica solo da quale CV è emersa la keyword."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> list[AtsKeywordItem]:
        result = await self._session.execute(
            select(AtsKeywordItem).order_by(AtsKeywordItem.created_at.asc())
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

    async def mark_present_as_added(self, cv_text: str) -> int:
        """Segna come 'added' (con data) le keyword 'todo'/'gap' ora presenti nel CV.
        È l'auto-rilevamento: ad ogni nuovo CV, ciò che hai inserito risulta fatto."""
        items = await self.get_all()
        marked = 0
        for it in items:
            if it.status in ("todo", "gap") and _present(it.keyword, cv_text):
                it.status = "added"
                marked += 1
        if marked:
            await self._session.commit()
        return marked

    async def merge_keywords(self, cv_id: int, keywords: list[dict], cv_text: str = "") -> int:
        """Aggiunge come 'todo' solo le keyword nuove: non già in lista (per fingerprint)
        e non già presenti nel CV. Ritorna quante ne ha aggiunte."""
        existing = await self.get_all()
        seen = {it.fingerprint for it in existing}
        added = 0
        for kw in keywords:
            keyword = (kw.get("keyword") or "").strip()
            if not keyword:
                continue
            fp = _fingerprint(keyword)
            if fp in seen or _present(keyword, cv_text):
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

    async def get_handled(self) -> list[str]:
        """Keyword aggiunte/ignorate/segnate come gap — da non riproporre a Minerva."""
        items = await self.get_all()
        return [it.keyword for it in items if it.status in ("added", "ignored", "gap")]
