import io
import json
from unittest.mock import AsyncMock, patch

import pytest
from docx import Document


def _make_docx(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


MOCK_ANALYSIS = {
    "executive_summary": "Professionista IT con 30 anni di esperienza.",
    "target_roles": [
        {
            "title": "IT Manager",
            "match_percentage": 90,
            "reason": "Esperienza diretta nel ruolo.",
            "market_demand": "alto",
        }
    ],
    "skill_gaps": [
        {
            "skill": "Cloud Azure",
            "priority": "alta",
            "why_needed": "Richiesto dai top employer.",
            "how_to_acquire": "Microsoft AZ-900 certification",
            "estimated_time": "4 settimane",
        }
    ],
    "roadmap": [
        {
            "order": 1,
            "action": "Iscriversi al corso AZ-900 su Microsoft Learn",
            "category": "certificazione",
            "impact": "Sblocca ruoli cloud-enabled",
            "timeframe": "questa settimana",
        }
    ],
}


MOCK_PARSED_DATA = {
    "full_name": "Mario Rossi", "email": None, "phone": None, "location": None,
    "summary": "IT Manager", "skills": ["Python", "Azure"], "work_experience": [],
    "education": [], "languages": [], "certifications": [],
}


async def _create_parsed_cv(client, db_session):
    """Upload a CV and directly set it as parsed in the test DB, bypassing Ollama."""
    content = _make_docx("Mario Rossi\nIT Manager\nPython, Azure, SAP")
    resp = await client.post(
        "/api/v1/cv/upload",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 201
    cv_id = resp.json()["id"]

    # Set status directly in the test DB session
    from app.repositories.cv_repository import CVRepository
    repo = CVRepository(db_session)
    await repo.update_parsed_data(cv_id, MOCK_PARSED_DATA)

    return cv_id


@pytest.mark.asyncio
async def test_analyze_cv_not_found(client):
    response = await client.post("/api/v1/cv/999/analyze")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyze_cv_not_parsed_yet(client):
    content = _make_docx("Mario Rossi\nIT Manager")
    resp = await client.post(
        "/api/v1/cv/upload",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    cv_id = resp.json()["id"]
    response = await client.post(f"/api/v1/cv/{cv_id}/analyze")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_analyze_returns_202(client, db_session):
    cv_id = await _create_parsed_cv(client, db_session)
    with patch("app.agents.career_strategist.agent.analyze", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = MOCK_ANALYSIS
        response = await client.post(f"/api/v1/cv/{cv_id}/analyze")
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "analyzing"
    assert "analysis_id" in data


@pytest.mark.asyncio
async def test_get_analysis_not_found(client):
    content = _make_docx("Test")
    resp = await client.post(
        "/api/v1/cv/upload",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    cv_id = resp.json()["id"]
    response = await client.get(f"/api/v1/cv/{cv_id}/analysis/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_analyses_empty(client):
    content = _make_docx("Test")
    resp = await client.post(
        "/api/v1/cv/upload",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    cv_id = resp.json()["id"]
    response = await client.get(f"/api/v1/cv/{cv_id}/analysis")
    assert response.status_code == 200
    assert response.json() == []
