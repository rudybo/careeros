import json

import pytest
from pydantic import ValidationError

from app.models.cv import CV
from app.repositories.application_repository import ApplicationRepository
from app.schemas.application import JobApplicationCreate


async def _cv(db_session) -> int:
    cv = CV(filename="a.pdf", raw_text="x", status="parsed", parsed_data="{}")
    db_session.add(cv)
    await db_session.commit()
    await db_session.refresh(cv)
    return cv.id


def test_create_schema_requires_text_or_url():
    with pytest.raises(ValidationError):
        JobApplicationCreate(cv_id=1)
    JobApplicationCreate(cv_id=1, source_url="https://x.it/job")
    JobApplicationCreate(cv_id=1, company="A", role="B", job_description="testo")


async def test_repo_meta_and_draft(db_session):
    repo = ApplicationRepository(db_session)
    cv_id = await _cv(db_session)
    app = await repo.create(cv_id, "Acme", "Dev", "jd", source_url="https://x.it/j")
    assert app.source_url == "https://x.it/j"
    assert app.draft_status == "idle"

    await repo.set_meta(app.id, "recruiter", "hr@acme.it")
    await repo.set_draft_status(app.id, "generating")
    updated = await repo.update_draft(
        app.id, {"full_name": "R"}, {"subject": "s", "full_text": "t"}, "https://mail.google.com/x"
    )
    assert updated.advertiser_type == "recruiter"
    assert updated.contact_email == "hr@acme.it"
    assert updated.draft_status == "ready"
    assert updated.draft_url == "https://mail.google.com/x"
    assert json.loads(updated.tailored_cv) == {"full_name": "R"}
    assert updated.cover_letter_status == "ready"
