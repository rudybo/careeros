"""Catalogo CV: kind, CV base, storico (archived)."""
import io
import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from docx import Document
from sqlalchemy import select

from app.core import database
from app.models.cv import CV
from app.repositories import cv_repository
from app.repositories.cv_repository import CVRepository, get_base_cv_id
from app.services import opportunity_application as oa
from app.services import telegram_service


async def _cv(db, status="parsed", **kw) -> int:
    cv = CV(filename=kw.pop("filename", "a.pdf"), raw_text="t", parsed_data='{"full_name": "R"}' if status == "parsed" else None,
            status=status, **kw)
    db.add(cv)
    await db.commit()
    await db.refresh(cv)
    return cv.id


def _factory(db_session):
    @asynccontextmanager
    async def _cm():
        yield db_session
    return _cm


def _docx() -> bytes:
    d = Document()
    d.add_paragraph("Mario Rossi Python")
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# -- repository --
async def test_new_cv_defaults(db_session):
    cv = await CVRepository(db_session).create("x.pdf", "txt")
    assert (cv.kind, cv.is_base, cv.archived) == ("altro", False, False)


async def test_set_kind_valid_and_invalid(db_session):
    repo = CVRepository(db_session)
    cid = await _cv(db_session)
    assert (await repo.set_kind(cid, "ats")).kind == "ats"
    with pytest.raises(ValueError):
        await repo.set_kind(cid, "boh")


async def test_set_base_moves_flag_keeps_one(db_session):
    repo = CVRepository(db_session)
    a, b = await _cv(db_session), await _cv(db_session)
    await repo.set_base(a)
    await repo.set_base(b)
    rows = (await db_session.execute(select(CV).where(CV.is_base.is_(True)))).scalars().all()
    assert [r.id for r in rows] == [b]
    assert (await repo.get_base()).id == b


async def test_set_base_rejects_archived_and_unparsed(db_session):
    repo = CVRepository(db_session)
    arch = await _cv(db_session, archived=True)
    unp = await _cv(db_session, status="uploaded")
    with pytest.raises(ValueError):
        await repo.set_base(arch)
    with pytest.raises(ValueError):
        await repo.set_base(unp)


async def test_archive_refuses_base_and_unarchive(db_session):
    repo = CVRepository(db_session)
    a, b = await _cv(db_session), await _cv(db_session)
    await repo.set_base(a)
    with pytest.raises(ValueError, match="imposta prima un altro CV come base"):
        await repo.archive(a)
    assert (await repo.archive(b)).archived is True
    assert (await repo.unarchive(b)).archived is False


async def test_get_all_include_archived(db_session):
    repo = CVRepository(db_session)
    a, b = await _cv(db_session), await _cv(db_session, archived=True)
    assert {c.id for c in await repo.get_all()} == {a, b}
    assert {c.id for c in await repo.get_all(include_archived=False)} == {a}


async def test_get_base_ignores_archived_flagged(db_session):
    await _cv(db_session, is_base=True, archived=True)
    assert await CVRepository(db_session).get_base() is None


# -- get_base_cv_id --
async def test_get_base_cv_id_returns_base(db_session):
    await _cv(db_session)
    b = await _cv(db_session, is_base=True)
    assert await get_base_cv_id(db_session) == b


async def test_get_base_cv_id_fallback_lowest_active_parsed(db_session, caplog):
    await _cv(db_session, archived=True)
    await _cv(db_session, status="uploaded")
    c = await _cv(db_session)
    await _cv(db_session)
    with caplog.at_level(logging.WARNING):
        assert await get_base_cv_id(db_session) == c
    assert any(r.levelno == logging.WARNING for r in caplog.records)


async def test_get_base_cv_id_none(db_session):
    assert await get_base_cv_id(db_session) is None


# -- migration --
async def test_migration_sets_lowest_parsed_active_once(db_session):
    await _cv(db_session, status="uploaded")
    await _cv(db_session, archived=True)
    c = await _cv(db_session)
    await _cv(db_session)
    conn = await db_session.connection()
    await database._migrate_base_cv(conn)
    await db_session.commit()
    rows = (await db_session.execute(select(CV.id).where(CV.is_base.is_(True)))).scalars().all()
    assert rows == [c]
    # idempotente / non sovrascrive una scelta successiva
    await CVRepository(db_session).set_base(c + 1)
    conn = await db_session.connection()
    await database._migrate_base_cv(conn)
    await db_session.commit()
    rows = (await db_session.execute(select(CV.id).where(CV.is_base.is_(True)))).scalars().all()
    assert rows == [c + 1]


async def test_migration_noop_without_parsed(db_session):
    await _cv(db_session, status="uploaded")
    await database._migrate_base_cv(await db_session.connection())
    await db_session.commit()
    assert (await db_session.execute(select(CV).where(CV.is_base.is_(True)))).first() is None


# -- API --
async def test_upload_with_kind_and_default(client):
    r = await client.post("/api/v1/cv/upload", files={"file": ("cv.docx", _docx(), _MIME)}, data={"kind": "breve"})
    assert r.status_code == 201
    assert r.json()["kind"] == "breve" and r.json()["is_base"] is False and r.json()["archived"] is False
    r = await client.post("/api/v1/cv/upload", files={"file": ("cv.docx", _docx(), _MIME)})
    assert r.json()["kind"] == "altro"


async def test_upload_invalid_kind_422(client):
    r = await client.post("/api/v1/cv/upload", files={"file": ("cv.docx", _docx(), _MIME)}, data={"kind": "zzz"})
    assert r.status_code == 422


async def test_list_filter_archived(client, db_session):
    a = await _cv(db_session)
    b = await _cv(db_session, archived=True)
    r = await client.get("/api/v1/cv/")
    assert {c["id"] for c in r.json()} == {a, b}
    assert {"kind", "is_base", "archived"} <= set(r.json()[0])
    assert [c["id"] for c in (await client.get("/api/v1/cv/?archived=false")).json()] == [a]
    assert [c["id"] for c in (await client.get("/api/v1/cv/?archived=true")).json()] == [b]


async def test_patch_partial_kind_only(client, db_session):
    a = await _cv(db_session)
    r = await client.patch(f"/api/v1/cv/{a}", json={"kind": "europass"})
    assert r.status_code == 200
    assert r.json()["kind"] == "europass" and r.json()["is_base"] is False


async def test_patch_base_archive_rules(client, db_session):
    a, b = await _cv(db_session), await _cv(db_session)
    assert (await client.patch(f"/api/v1/cv/{a}", json={"is_base": True})).json()["is_base"] is True
    r = await client.patch(f"/api/v1/cv/{a}", json={"archived": True})
    assert r.status_code == 409 and "imposta prima un altro CV come base" in r.json()["detail"]
    r = await client.patch(f"/api/v1/cv/{a}", json={"is_base": False})
    assert r.status_code == 409
    assert (await client.patch(f"/api/v1/cv/{b}", json={"archived": True})).json()["archived"] is True
    r = await client.patch(f"/api/v1/cv/{b}", json={"is_base": True})
    assert r.status_code == 409
    assert (await client.patch(f"/api/v1/cv/{b}", json={"archived": False})).json()["archived"] is False


async def test_patch_invalid_kind_and_404(client, db_session):
    a = await _cv(db_session)
    assert (await client.patch(f"/api/v1/cv/{a}", json={"kind": "boh"})).status_code == 422
    assert (await client.patch("/api/v1/cv/999", json={"kind": "ats"})).status_code == 404


async def test_get_detail_exposes_flags(client, db_session):
    a = await _cv(db_session, kind="ats", is_base=True)
    d = (await client.get(f"/api/v1/cv/{a}")).json()
    assert (d["kind"], d["is_base"], d["archived"]) == ("ats", True, False)


async def test_delete_base_refused_409_others_ok(client, db_session):
    a, b = await _cv(db_session, is_base=True), await _cv(db_session)
    r = await client.delete(f"/api/v1/cv/{a}")
    assert r.status_code == 409 and "imposta prima un altro CV come base" in r.json()["detail"]
    assert (await client.delete(f"/api/v1/cv/{b}")).status_code == 204


# -- consumers use the base id --
async def test_telegram_draft_uses_base_id(db_session):
    base = await _cv(db_session, is_base=True)
    from app.repositories.market_repository import OpportunityRepository
    repo = OpportunityRepository(db_session)
    await repo.upsert_many([{"external_id": "e", "title": "Dev", "company": "Acme", "url": "https://x", "description": "d"}])
    oid = (await repo.get_all())[0].id
    with patch("app.core.database.AsyncSessionLocal", _factory(db_session)), \
         patch("app.api.v1.endpoints.market._run_create_draft", new=AsyncMock(return_value=None)) as run, \
         patch.object(telegram_service, "send_text", new=AsyncMock()):
        await telegram_service._do_draft(oid)
    assert run.await_args.kwargs["cv_id"] == base


async def test_telegram_draft_no_base_warns(db_session):
    with patch("app.core.database.AsyncSessionLocal", _factory(db_session)), \
         patch.object(telegram_service, "send_text", new=AsyncMock()) as st:
        await telegram_service._do_draft(1)
    assert "CV mancante" in st.await_args.args[0]


async def test_telegram_applied_uses_base_id(db_session):
    base = await _cv(db_session, is_base=True)
    with patch("app.core.database.AsyncSessionLocal", _factory(db_session)), \
         patch.object(oa, "mark_applied", new=AsyncMock(return_value=object())) as ma, \
         patch.object(telegram_service, "_answer_callback", new=AsyncMock()), \
         patch.object(telegram_service, "send_text", new=AsyncMock()):
        await telegram_service._handle_callback({"id": "c", "data": "applied:5"})
    assert ma.await_args.args[1:] == (5, base)


async def test_market_draft_default_and_explicit_cv(client, db_session):
    base = await _cv(db_session, is_base=True)
    other = await _cv(db_session)
    from app.repositories.market_repository import OpportunityRepository
    repo = OpportunityRepository(db_session)
    await repo.upsert_many([{"external_id": "e", "title": "Dev", "company": "Acme", "url": "https://x", "description": "d"}])
    oid = (await repo.get_all())[0].id
    with patch("app.api.v1.endpoints.market._run_create_draft", new=AsyncMock()) as run:
        r = await client.post(f"/api/v1/market/opportunities/{oid}/draft")
        assert r.status_code == 202 and run.await_args.kwargs["cv_id"] == base
        await repo.update_draft_status(oid, "none")
        r = await client.post(f"/api/v1/market/opportunities/{oid}/draft?cv_id={other}")
        assert r.status_code == 202 and run.await_args.kwargs["cv_id"] == other


async def test_market_draft_no_base_409(client, db_session):
    from app.repositories.market_repository import OpportunityRepository
    repo = OpportunityRepository(db_session)
    await repo.upsert_many([{"external_id": "e", "title": "Dev", "company": "Acme", "url": "https://x", "description": "d"}])
    oid = (await repo.get_all())[0].id
    r = await client.post(f"/api/v1/market/opportunities/{oid}/draft")
    assert r.status_code == 409


async def test_telegram_applied_never_raises(db_session):
    await _cv(db_session, is_base=True)
    with patch("app.core.database.AsyncSessionLocal", _factory(db_session)),          patch.object(oa, "mark_applied", new=AsyncMock(side_effect=ValueError("db"))),          patch.object(telegram_service, "_answer_callback", new=AsyncMock()) as ans,          patch.object(telegram_service, "send_text", new=AsyncMock()):
        await telegram_service._handle_callback({"id": "c", "data": "applied:5"})
    assert ans.await_args.args[1] == "⚠️ Errore"


async def test_pick_cv_for_scheduled_search_prefers_base(db_session):
    from app.main import _pick_cv_for_scheduled_search
    assert await _pick_cv_for_scheduled_search(db_session) is None
    first = await _cv(db_session)
    base = await _cv(db_session, is_base=True)
    await _cv(db_session)  # piu' recente, non base
    picked = await _pick_cv_for_scheduled_search(db_session)
    assert picked.id == base
    assert picked.id != first
