from unittest.mock import AsyncMock, patch

from app.agents.job_parser.agent import JobMeta
from app.services.job_fetcher import JobFetchError
from tests.test_applications import _create_parsed_cv


async def test_create_from_url_fills_meta(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    meta = JobMeta(company="Acme", role="Dev", advertiser_type="recruiter", contact_email="hr@acme.it")
    with patch("app.api.v1.endpoints.application.fetch_job_posting", new=AsyncMock(return_value="testo annuncio")), \
         patch("app.api.v1.endpoints.application.job_parser.parse", new=AsyncMock(return_value=meta)):
        r = await client.post("/api/v1/applications/", json={"cv_id": cv_id, "source_url": "https://x.it/j"})
    assert r.status_code == 201, r.text
    detail = await client.get(f"/api/v1/applications/{r.json()['id']}")
    d = detail.json()
    assert d["company"] == "Acme" and d["advertiser_type"] == "recruiter"
    assert d["contact_email"] == "hr@acme.it" and d["source_url"] == "https://x.it/j"
    assert d["job_description"] == "testo annuncio"


async def test_create_from_url_fetch_failure_is_422(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    with patch("app.api.v1.endpoints.application.fetch_job_posting",
               new=AsyncMock(side_effect=JobFetchError("incolla il testo"))):
        r = await client.post("/api/v1/applications/", json={"cv_id": cv_id, "source_url": "https://x.it/j"})
    assert r.status_code == 422
    assert "incolla" in r.json()["detail"]


async def test_create_without_text_or_url_is_422(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    r = await client.post("/api/v1/applications/", json={"cv_id": cv_id})
    assert r.status_code == 422


async def test_patch_meta_and_start_draft(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    r = await client.post("/api/v1/applications/", json={
        "cv_id": cv_id, "company": "Acme", "role": "Dev", "job_description": "jd"})
    app_id = r.json()["id"]

    p = await client.patch(f"/api/v1/applications/{app_id}", json={"advertiser_type": "direct", "contact_email": "a@b.it"})
    assert p.status_code == 200
    d = (await client.get(f"/api/v1/applications/{app_id}")).json()
    assert d["advertiser_type"] == "direct" and d["contact_email"] == "a@b.it"

    started = await client.post(f"/api/v1/applications/{app_id}/draft")
    assert started.status_code == 202
    d = (await client.get(f"/api/v1/applications/{app_id}")).json()
    assert d["draft_status"] == "generating"
    again = await client.post(f"/api/v1/applications/{app_id}/draft")
    assert again.status_code == 409


async def _new_app(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    r = await client.post("/api/v1/applications/", json={
        "cv_id": cv_id, "company": "Acme", "role": "Dev", "job_description": "jd"})
    return r.json()["id"]


async def test_patch_partial_keeps_other_field(client, db_session):
    app_id = await _new_app(client, db_session)
    await client.patch(f"/api/v1/applications/{app_id}", json={"advertiser_type": "direct", "contact_email": "a@b.it"})
    p = await client.patch(f"/api/v1/applications/{app_id}", json={"advertiser_type": "recruiter"})
    assert p.status_code == 200
    d = (await client.get(f"/api/v1/applications/{app_id}")).json()
    assert d["advertiser_type"] == "recruiter" and d["contact_email"] == "a@b.it"


async def test_patch_explicit_null_clears(client, db_session):
    app_id = await _new_app(client, db_session)
    await client.patch(f"/api/v1/applications/{app_id}", json={"advertiser_type": "direct", "contact_email": "a@b.it"})
    await client.patch(f"/api/v1/applications/{app_id}", json={"contact_email": None})
    d = (await client.get(f"/api/v1/applications/{app_id}")).json()
    assert d["contact_email"] is None and d["advertiser_type"] == "direct"


async def test_patch_unknown_id_404(client):
    r = await client.patch("/api/v1/applications/99999", json={"contact_email": "a@b.it"})
    assert r.status_code == 404


async def test_draft_unknown_id_404(client):
    r = await client.post("/api/v1/applications/99999/draft")
    assert r.status_code == 404


async def test_draft_unparsed_cv_409(client, db_session):
    from app.models.cv import CV
    cv = CV(filename="x.pdf", raw_text="t", parsed_data=None, status="parsed")
    db_session.add(cv)
    await db_session.commit()
    await db_session.refresh(cv)
    r = await client.post("/api/v1/applications/", json={
        "cv_id": cv.id, "company": "Acme", "role": "Dev", "job_description": "jd"})
    assert r.status_code == 201, r.text
    d = await client.post(f"/api/v1/applications/{r.json()['id']}/draft")
    assert d.status_code == 409
