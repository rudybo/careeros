import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import ApplicationDocument, JobApplication


class ApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        cv_id: int,
        company: str,
        role: str,
        job_description: str,
        source_url: str | None = None,
        advertiser_type: str | None = None,
        contact_email: str | None = None,
    ) -> JobApplication:
        app = JobApplication(
            cv_id=cv_id,
            company=company,
            role=role,
            job_description=job_description,
            source_url=source_url,
            advertiser_type=advertiser_type,
            contact_email=contact_email,
            status="draft",
        )
        self._session.add(app)
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def get_by_opportunity_id(self, opp_id: int) -> JobApplication | None:
        result = await self._session.execute(
            select(JobApplication).where(JobApplication.opportunity_id == opp_id).order_by(JobApplication.id).limit(1)
        )
        return result.scalar_one_or_none()

    async def create_from_opportunity(
        self,
        cv_id: int,
        opportunity_id: int,
        company: str,
        role: str,
        job_description: str,
        source_url: str | None = None,
        advertiser_type: str | None = None,
        contact_email: str | None = None,
    ) -> JobApplication:
        app = JobApplication(
            cv_id=cv_id,
            opportunity_id=opportunity_id,
            company=company,
            role=role,
            job_description=job_description,
            source_url=source_url,
            advertiser_type=advertiser_type,
            contact_email=contact_email,
            status="draft",
        )
        self._session.add(app)
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def add_document(self, app_id: int, kind: str, filename: str, content: bytes) -> ApplicationDocument:
        doc = ApplicationDocument(
            application_id=app_id, kind=kind, filename=filename, content=content, size=len(content),
        )
        self._session.add(doc)
        await self._session.commit()
        await self._session.refresh(doc)
        return doc

    async def list_documents(self, app_id: int) -> list[ApplicationDocument]:
        """Metadati dei documenti (newest first), senza caricare `content`."""
        result = await self._session.execute(
            select(
                ApplicationDocument.id, ApplicationDocument.application_id, ApplicationDocument.kind,
                ApplicationDocument.filename, ApplicationDocument.size, ApplicationDocument.created_at,
            )
            .where(ApplicationDocument.application_id == app_id)
            .order_by(ApplicationDocument.id.desc())
        )
        return list(result.all())

    async def get_document(self, app_id: int, doc_id: int) -> ApplicationDocument | None:
        result = await self._session.execute(
            select(ApplicationDocument).where(
                ApplicationDocument.id == doc_id, ApplicationDocument.application_id == app_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _set_status(app: JobApplication, status: str) -> None:
        """Cambia lo stato e ne registra la data nello storico.

        Unico punto che scrive `status`: ogni transizione (anche quelle degli
        agenti, es. update_optimization → "ready") finisce nella cronologia.
        """
        now = datetime.now(timezone.utc)
        app.status = status
        if status == "applied":
            app.applied_at = now
        hist = json.loads(app.status_history) if app.status_history else []
        if hist and hist[-1]["status"] == status:
            return  # stesso stato consecutivo: niente riga duplicata
        hist.append({"status": status, "at": now.isoformat()})
        app.status_history = json.dumps(hist, ensure_ascii=False)

    async def update_status(self, app_id: int, status: str) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        self._set_status(app, status)
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def set_thread_id(self, app_id: int, thread_id: str) -> None:
        app = await self.get_by_id(app_id)
        if app is not None:
            app.gmail_thread_id = thread_id
            await self._session.commit()

    async def mark_sent(self, app_id: int, sent_at: datetime) -> JobApplication | None:
        """Bozza inviata: stato 'applied' con data = invio reale (anche nello storico)."""
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        self._set_status(app, "applied")
        app.sent_at = sent_at
        app.applied_at = sent_at
        hist = json.loads(app.status_history) if app.status_history else []
        if hist and hist[-1]["status"] == "applied":
            hist[-1]["at"] = sent_at.isoformat()
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
            await self._session.execute(
                delete(ApplicationDocument).where(ApplicationDocument.application_id == app.id)
            )
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
        self._set_status(app, "ready")
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

    async def set_meta(self, app_id: int, advertiser_type: str | None, contact_email: str | None) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        app.advertiser_type = advertiser_type
        app.contact_email = contact_email
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def set_draft_status(self, app_id: int, status: str) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        app.draft_status = status
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def update_draft(
        self, app_id: int, tailored_cv: dict, cover_letter: dict, draft_url: str, thread_id: str | None = None,
    ) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        app.tailored_cv = json.dumps(tailored_cv, ensure_ascii=False)
        app.cover_letter = json.dumps(cover_letter, ensure_ascii=False)
        app.cover_letter_status = "ready"
        app.draft_url = draft_url
        if thread_id:
            app.gmail_thread_id = thread_id
        app.draft_status = "ready"
        await self._session.commit()
        await self._session.refresh(app)
        return app
