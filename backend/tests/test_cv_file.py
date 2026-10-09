"""Salvataggio del file originale del CV e apertura via GET /cv/{id}/file."""
from unittest.mock import patch

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import attributes

from app.core import database
from app.models.cv import CV
from app.repositories.cv_repository import CVRepository
from scripts import attach_cv_file

PDF = b"%PDF-1.4 fake bytes"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _upload(client, name="cv.pdf", content=PDF, text_="Mario Rossi Python"):
    with patch("app.api.v1.endpoints.cv.extract_text", return_value=text_):
        return await client.post("/api/v1/cv/upload", files={"file": (name, content, "application/octet-stream")})


async def test_upload_stores_and_serves_pdf(client, db_session):
    r = await _upload(client)
    assert r.status_code == 201 and r.json()["has_file"] is True
    cv_id = r.json()["id"]
    f = await client.get(f"/api/v1/cv/{cv_id}/file")
    assert f.status_code == 200 and f.content == PDF
    assert f.headers["content-type"].startswith("application/pdf")
    assert f.headers["content-disposition"] == 'inline; filename="cv.pdf"'
    row = (await db_session.execute(select(CV).where(CV.id == cv_id))).scalar_one()
    assert row.file_mime == "application/pdf" and row.file_size == len(PDF)


async def test_docx_is_attachment(client):
    r = await _upload(client, name="cv.docx", content=b"PK docx")
    f = await client.get(f"/api/v1/cv/{r.json()['id']}/file")
    assert f.headers["content-type"].startswith(DOCX_MIME)
    assert f.headers["content-disposition"].startswith("attachment;")


async def test_file_404s(client, db_session):
    assert (await client.get("/api/v1/cv/999/file")).status_code == 404
    cv = await CVRepository(db_session).create("n.pdf", "t")
    assert (await client.get(f"/api/v1/cv/{cv.id}/file")).status_code == 404


async def test_filename_sanitised(client):
    r = await _upload(client, name='c"v\è\r\n.pdf')
    f = await client.get(f"/api/v1/cv/{r.json()['id']}/file")
    cd = f.headers["content-disposition"]
    assert cd.isascii() and "\\" not in cd and "\n" not in cd and cd.count('"') == 2
    assert "_" in cd


async def test_has_file_in_list_and_detail(client, db_session):
    a = (await _upload(client)).json()["id"]
    b = (await CVRepository(db_session).create("x.pdf", "t")).id
    lst = {c["id"]: c["has_file"] for c in (await client.get("/api/v1/cv/")).json()}
    assert lst[a] is True and lst[b] is False
    assert (await client.get(f"/api/v1/cv/{a}")).json()["has_file"] is True
    assert (await client.get(f"/api/v1/cv/{b}")).json()["has_file"] is False


async def test_get_all_does_not_load_blob(db_session):
    repo = CVRepository(db_session)
    cv = await repo.create("a.pdf", "t", file_content=PDF, file_mime="application/pdf")
    db_session.expunge_all()
    cvs = await repo.get_all()
    assert "file_content" in attributes.instance_state(cvs[0]).unloaded
    assert cvs[0].has_file is True
    assert (await repo.get_file(cv.id)) == ("a.pdf", "application/pdf", PDF)


async def test_migration_adds_columns_on_old_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE cvs (id INTEGER PRIMARY KEY, filename VARCHAR(255))"))
        for t in ("job_applications", "job_opportunities", "user_preferences"):
            await conn.execute(text(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY)"))
        await database._migrate_add_columns(conn)
        cols = [r[1] for r in (await conn.execute(text("PRAGMA table_info(cvs)"))).all()]
    await engine.dispose()
    assert {"file_content", "file_mime", "file_size"} <= set(cols)


# -- script attach --
async def _cv(db_session, raw="Mario Rossi sviluppatore Python " * 20):
    return (await CVRepository(db_session).create("old.pdf", raw)).id


async def test_attach_matching(db_session, tmp_path):
    cv_id = await _cv(db_session)
    p = tmp_path / "cv.pdf"
    p.write_bytes(PDF)
    with patch.object(attach_cv_file, "extract_text", return_value="Mario  Rossi sviluppatore Python " * 20):
        res = await attach_cv_file.attach(cv_id, str(p), db_session)
    assert res["attached"] is True and res["size"] == len(PDF)
    assert (await CVRepository(db_session).get_file(cv_id))[2] == PDF


async def test_attach_refuses_different_and_force(db_session, tmp_path):
    cv_id = await _cv(db_session)
    p = tmp_path / "cv.pdf"
    p.write_bytes(PDF)
    with patch.object(attach_cv_file, "extract_text", return_value="completamente altro testo qwerty zxcvb " * 20):
        res = await attach_cv_file.attach(cv_id, str(p), db_session)
        assert res["attached"] is False and res["similarity"] < 0.85
        assert await CVRepository(db_session).get_file(cv_id) is None or (await CVRepository(db_session).get_file(cv_id))[2] in (None, b"")
        res = await attach_cv_file.attach(cv_id, str(p), db_session, force=True)
    assert res["attached"] is True
