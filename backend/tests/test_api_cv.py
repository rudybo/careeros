import io

import pytest
from docx import Document


def _make_docx(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_upload_cv_unsupported_format(client):
    response = await client.post(
        "/api/v1/cv/upload",
        files={"file": ("cv.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_cv_docx_success(client):
    content = _make_docx("Mario Rossi\nSoftware Engineer\nPython, FastAPI")
    response = await client.post(
        "/api/v1/cv/upload",
        files={"file": ("cv.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "cv.docx"
    assert data["status"] == "uploaded"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_cv_not_found(client):
    response = await client.get("/api/v1/cv/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_cvs_empty(client):
    response = await client.get("/api/v1/cv/")
    assert response.status_code == 200
    assert response.json() == []
