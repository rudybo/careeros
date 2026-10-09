import json
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cv import CV

logger = logging.getLogger(__name__)

CV_KINDS = ("completo", "breve", "ats", "europass", "altro")
BASE_BLOCK_MSG = "Questo è il CV base: imposta prima un altro CV come base."


class CVRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, filename: str, raw_text: str, file_content: bytes | None = None, file_mime: str | None = None
    ) -> CV:
        cv = CV(filename=filename, raw_text=raw_text, status="uploaded")
        if file_content:
            cv.file_content, cv.file_mime, cv.file_size = file_content, file_mime, len(file_content)
        self._session.add(cv)
        await self._session.commit()
        await self._session.refresh(cv)
        return cv

    async def attach_file(self, cv_id: int, content: bytes, mime: str) -> CV | None:
        cv = await self.get_by_id(cv_id)
        if cv is None:
            return None
        cv.file_content, cv.file_mime, cv.file_size = content, mime, len(content)
        await self._session.commit()
        await self._session.refresh(cv)
        return cv

    async def get_file(self, cv_id: int) -> tuple[str, str, bytes] | None:
        row = (
            await self._session.execute(
                select(CV.filename, CV.file_mime, CV.file_content).where(CV.id == cv_id)
            )
        ).first()
        if row is None or not row.file_content:
            return None
        return row.filename, row.file_mime or "application/octet-stream", bytes(row.file_content)

    async def update_parsed_data(self, cv_id: int, parsed_data: dict) -> CV | None:
        cv = await self.get_by_id(cv_id)
        if cv is None:
            return None
        cv.parsed_data = json.dumps(parsed_data)
        cv.status = "parsed"
        await self._session.commit()
        await self._session.refresh(cv)
        return cv

    async def update_raw_text(self, cv_id: int, raw_text: str) -> CV | None:
        cv = await self.get_by_id(cv_id)
        if cv is None:
            return None
        cv.raw_text = raw_text
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

    async def delete(self, cv_id: int) -> bool:
        cv = await self.get_by_id(cv_id)
        if cv is None:
            return False
        if cv.is_base:
            raise ValueError(BASE_BLOCK_MSG)
        await self._session.delete(cv)
        await self._session.commit()
        return True

    async def get_all(self, include_archived: bool = True) -> list[CV]:
        stmt = select(CV).order_by(CV.created_at.desc())
        if not include_archived:
            stmt = stmt.where(CV.archived.is_(False))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_base(self) -> CV | None:
        result = await self._session.execute(
            select(CV).where(CV.is_base.is_(True), CV.archived.is_(False), CV.status == "parsed").limit(1)
        )
        return result.scalar_one_or_none()

    async def set_kind(self, cv_id: int, kind: str) -> CV | None:
        if kind not in CV_KINDS:
            raise ValueError(f"Tipo non valido. Valori: {list(CV_KINDS)}")
        cv = await self.get_by_id(cv_id)
        if cv is None:
            return None
        cv.kind = kind
        await self._session.commit()
        await self._session.refresh(cv)
        return cv

    async def set_base(self, cv_id: int) -> CV | None:
        cv = await self.get_by_id(cv_id)
        if cv is None:
            return None
        if cv.archived or cv.status != "parsed":
            raise ValueError("Solo un CV attivo e già analizzato può essere il CV base.")
        await self._session.execute(update(CV).where(CV.id != cv_id).values(is_base=False))
        cv.is_base = True
        await self._session.commit()
        await self._session.refresh(cv)
        return cv

    async def archive(self, cv_id: int) -> CV | None:
        cv = await self.get_by_id(cv_id)
        if cv is None:
            return None
        if cv.is_base:
            raise ValueError(BASE_BLOCK_MSG)
        cv.archived = True
        await self._session.commit()
        await self._session.refresh(cv)
        return cv

    async def unarchive(self, cv_id: int) -> CV | None:
        cv = await self.get_by_id(cv_id)
        if cv is None:
            return None
        cv.archived = False
        await self._session.commit()
        await self._session.refresh(cv)
        return cv


async def get_base_cv_id(session: AsyncSession) -> int | None:
    """Id del CV base; fallback (WARNING) al CV parsato attivo con id minore; None se non c'e'."""
    base = await CVRepository(session).get_base()
    if base is not None:
        return base.id
    result = await session.execute(
        select(CV.id).where(CV.archived.is_(False), CV.status == "parsed").order_by(CV.id).limit(1)
    )
    fallback = result.scalar_one_or_none()
    if fallback is not None:
        logger.warning("Nessun CV base impostato: uso il CV %d come fallback.", fallback)
    return fallback
