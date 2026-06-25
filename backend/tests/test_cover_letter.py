"""Integration tests for cover letter endpoint."""
import json
import pytest
from app.models.cv import CV
from app.models.application import JobApplication

JD = "We need a Senior Python Developer with FastAPI and Docker experience."

OPT = {
    "match_score": 70,
    "matched_keywords": ["Python", "FastAPI"],
    "missing_keywords": ["Docker"],
    "ats_warnings": [],
    "section_suggestions": [],
    "cover_letter_hints": ["Esperienza con FastAPI", "Team lead", "Progetti internazionali"],
    "optimized_summary": "Backend developer with FastAPI expertise.",
}


async def _create_ready_app(db_session) -> int:
    parsed_data = {
        "full_name": "Rudy Botosso", "email": "rudy@test.com", "phone": None,
        "summary": "Backend developer", "skills": ["Python", "FastAPI"],
        "languages": ["Italian"], "work_experience": [], "education": [], "certifications": [],
    }
    cv = CV(filename="rudy.pdf", raw_text="text", parsed_data=json.dumps(parsed_data), status="parsed")
    db_session.add(cv)
    await db_session.commit()
    await db_session.refresh(cv)

    app = JobApplication(
        cv_id=cv.id, company="TechCorp", role="Python Developer",
        job_description=JD, status="ready",
        optimization_data=json.dumps(OPT),
        cover_letter_status="idle",
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    return app.id


@pytest.mark.asyncio
async def test_generate_cover_letter_returns_202(client, db_session):
    app_id = await _create_ready_app(db_session)
    response = await client.post(f"/api/v1/applications/{app_id}/cover-letter")
    assert response.status_code == 202
    data = response.json()
    assert data["cover_letter_status"] == "generating"
    assert data["application_id"] == app_id


@pytest.mark.asyncio
async def test_generate_cover_letter_not_found(client):
    response = await client.post("/api/v1/applications/9999/cover-letter")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_cover_letter_not_ready(client, db_session):
    parsed_data = {
        "full_name": "Test User", "email": None, "phone": None, "summary": None,
        "skills": [], "languages": [], "work_experience": [], "education": [], "certifications": [],
    }
    cv = CV(filename="test.pdf", raw_text="x", parsed_data=json.dumps(parsed_data), status="parsed")
    db_session.add(cv)
    await db_session.commit()
    await db_session.refresh(cv)

    app = JobApplication(
        cv_id=cv.id, company="X", role="Y", job_description=JD,
        status="draft", cover_letter_status="idle",
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)

    response = await client.post(f"/api/v1/applications/{app.id}/cover-letter")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_generate_cover_letter_already_generating(client, db_session):
    app_id = await _create_ready_app(db_session)
    # First request sets status to generating
    await client.post(f"/api/v1/applications/{app_id}/cover-letter")
    # Second request should 409
    response = await client.post(f"/api/v1/applications/{app_id}/cover-letter")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_application_detail_includes_cover_letter_status(client, db_session):
    app_id = await _create_ready_app(db_session)
    response = await client.get(f"/api/v1/applications/{app_id}")
    assert response.status_code == 200
    data = response.json()
    assert "cover_letter_status" in data
    assert data["cover_letter_status"] == "idle"
    assert data["cover_letter"] is None
