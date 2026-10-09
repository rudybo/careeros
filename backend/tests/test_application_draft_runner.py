import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from app.repositories.application_repository import ApplicationRepository
from app.services import application_draft
from tests.test_applications import _create_parsed_cv


def _factory(db_session):
    @asynccontextmanager
    async def _cm():
        yield db_session
    return _cm


async def _make_app(db_session):
    cv_id = await _create_parsed_cv(db_session)
    repo = ApplicationRepository(db_session)
    rec = await repo.create(cv_id=cv_id, company="Acme", role="Dev", job_description="jd")
    return repo, rec.id


async def test_runner_success(db_session):
    repo, app_id = await _make_app(db_session)
    res = {
        "tailored_cv": {"full_name": "Rudy Botosso", "email": "r@x.it", "skills": ["Python"]},
        "cover_letter": {"subject": "s", "full_text": "t"},
        "draft_id": "d1", "gmail_url": "https://mail/d1",
        "advertiser_type": "direct", "contact_email": "hr@acme.it",
        "pdf_bytes": b"%PDF-r", "pdf_filename": "CV_Rudy_Botosso.pdf",
    }
    with patch.object(application_draft, "AsyncSessionLocal", _factory(db_session)), \
         patch.object(application_draft, "build_tailored_draft", new=AsyncMock(return_value=res)):
        await application_draft.run_application_draft(app_id)
    rec = await repo.get_by_id(app_id)
    assert rec.draft_status == "ready"
    assert json.loads(rec.tailored_cv)["full_name"] == "Rudy Botosso"
    assert rec.draft_url == "https://mail/d1"
    assert rec.advertiser_type == "direct" and rec.contact_email == "hr@acme.it"
    docs = await repo.list_documents(app_id)
    assert len(docs) == 1 and docs[0].filename == "CV_Rudy_Botosso.pdf" and docs[0].kind == "cv_su_misura"


async def test_runner_failure_sets_error(db_session):
    repo, app_id = await _make_app(db_session)
    with patch.object(application_draft, "AsyncSessionLocal", _factory(db_session)), \
         patch.object(application_draft, "build_tailored_draft", new=AsyncMock(side_effect=RuntimeError("boom"))):
        await application_draft.run_application_draft(app_id)
    assert (await repo.get_by_id(app_id)).draft_status == "error"


async def test_runner_missing_record_does_not_raise(db_session):
    with patch.object(application_draft, "AsyncSessionLocal", _factory(db_session)), \
         patch.object(application_draft, "build_tailored_draft", new=AsyncMock()) as b:
        await application_draft.run_application_draft(99999)
    b.assert_not_called()


async def test_runner_attachment_failure_keeps_ready(db_session):
    repo, app_id = await _make_app(db_session)
    res = {
        "tailored_cv": {"full_name": "R", "email": "r@x.it", "skills": ["Python"]},
        "cover_letter": {"subject": "s", "full_text": "t"},
        "draft_id": "d1", "gmail_url": "https://mail/d1",
        "advertiser_type": "direct", "contact_email": "hr@acme.it",
        "pdf_bytes": b"%PDF-r", "pdf_filename": "CV.pdf",
    }
    with patch.object(application_draft, "AsyncSessionLocal", _factory(db_session)),          patch.object(application_draft, "build_tailored_draft", new=AsyncMock(return_value=res)),          patch.object(ApplicationRepository, "add_document", new=AsyncMock(side_effect=ValueError("disk"))):
        await application_draft.run_application_draft(app_id)
    rec = await repo.get_by_id(app_id)
    assert rec.draft_status == "ready" and rec.draft_url == "https://mail/d1"
