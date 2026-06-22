"""Integration tests for /applications endpoints."""
import json

import pytest
import pytest_asyncio

from app.models.cv import CV


async def _create_parsed_cv(db_session) -> int:
    """Helper: insert a CV in 'parsed' state into the test DB."""
    parsed_data = {
        "full_name": "Rudy Botosso",
        "email": "rudy@example.com",
        "phone": None,
        "summary": "Backend developer",
        "skills": ["Python", "FastAPI", "SQL"],
        "languages": ["Italiano", "Inglese"],
        "work_experience": [
            {
                "company": "Acme",
                "role": "Backend Developer",
                "start_date": "2022",
                "end_date": None,
                "description": "Built REST APIs with FastAPI and Python.",
            }
        ],
        "education": [
            {
                "institution": "University of Milan",
                "degree": "Bachelor",
                "field": "Computer Science",
                "year": "2021",
            }
        ],
        "certifications": [],
    }
    cv = CV(
        filename="rudy.pdf",
        raw_text="sample text",
        parsed_data=json.dumps(parsed_data),
        status="parsed",
    )
    db_session.add(cv)
    await db_session.commit()
    await db_session.refresh(cv)
    return cv.id


JD = """
We are looking for a Senior Python Developer with strong experience in FastAPI,
PostgreSQL, and Docker. Knowledge of Redis and Kubernetes is a plus.
The candidate must have experience with REST APIs and microservices architecture.
"""


@pytest.mark.asyncio
async def test_create_application(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    response = await client.post(
        "/api/v1/applications/",
        json={"cv_id": cv_id, "company": "TechCorp", "role": "Python Developer", "job_description": JD},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["company"] == "TechCorp"
    assert data["role"] == "Python Developer"
    assert data["status"] == "draft"
    assert data["cv_id"] == cv_id


@pytest.mark.asyncio
async def test_create_application_cv_not_found(client):
    response = await client.post(
        "/api/v1/applications/",
        json={"cv_id": 9999, "company": "X", "role": "Y", "job_description": JD},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_application_cv_not_parsed(client, db_session):
    cv = CV(filename="draft.pdf", raw_text="text", parsed_data=None, status="pending")
    db_session.add(cv)
    await db_session.commit()
    await db_session.refresh(cv)

    response = await client.post(
        "/api/v1/applications/",
        json={"cv_id": cv.id, "company": "X", "role": "Y", "job_description": JD},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_analyze_application(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    create = await client.post(
        "/api/v1/applications/",
        json={"cv_id": cv_id, "company": "TechCorp", "role": "Dev", "job_description": JD},
    )
    app_id = create.json()["id"]

    response = await client.post(f"/api/v1/applications/{app_id}/analyze")
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "analyzing"
    assert "application_id" in data


@pytest.mark.asyncio
async def test_analyze_application_not_found(client):
    response = await client.post("/api/v1/applications/9999/analyze")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_application_without_optimization(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    create = await client.post(
        "/api/v1/applications/",
        json={"cv_id": cv_id, "company": "TestCo", "role": "Dev", "job_description": JD},
    )
    app_id = create.json()["id"]

    response = await client.get(f"/api/v1/applications/{app_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["optimization"] is None
    assert data["company"] == "TestCo"
    assert data["job_description"] == JD


@pytest.mark.asyncio
async def test_list_applications(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    await client.post(
        "/api/v1/applications/",
        json={"cv_id": cv_id, "company": "A", "role": "Dev", "job_description": JD},
    )
    await client.post(
        "/api/v1/applications/",
        json={"cv_id": cv_id, "company": "B", "role": "Dev", "job_description": JD},
    )

    response = await client.get("/api/v1/applications/")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_update_status_to_applied(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    create = await client.post(
        "/api/v1/applications/",
        json={"cv_id": cv_id, "company": "X", "role": "Y", "job_description": JD},
    )
    app_id = create.json()["id"]

    response = await client.patch(f"/api/v1/applications/{app_id}/status", json={"status": "applied"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "applied"
    assert data["applied_at"] is not None


@pytest.mark.asyncio
async def test_update_status_invalid(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    create = await client.post(
        "/api/v1/applications/",
        json={"cv_id": cv_id, "company": "X", "role": "Y", "job_description": JD},
    )
    app_id = create.json()["id"]

    response = await client.patch(f"/api/v1/applications/{app_id}/status", json={"status": "flying"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analyze_already_analyzing(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    create = await client.post(
        "/api/v1/applications/",
        json={"cv_id": cv_id, "company": "X", "role": "Y", "job_description": JD},
    )
    app_id = create.json()["id"]

    # Primo analyze → 202
    await client.post(f"/api/v1/applications/{app_id}/analyze")
    # Secondo analyze sullo stesso app in stato "analyzing" → 409
    response = await client.post(f"/api/v1/applications/{app_id}/analyze")
    assert response.status_code == 409
