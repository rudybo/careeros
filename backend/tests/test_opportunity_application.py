import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from app.api.v1.endpoints import market as market_ep
from app.repositories.cv_repository import CVRepository
from app.repositories.application_repository import ApplicationRepository
from app.repositories.market_repository import OpportunityRepository
from app.services import opportunity_application as oa
from app.services import telegram_service
from tests.test_applications import _create_parsed_cv


def _factory(db_session):
    @asynccontextmanager
    async def _cm():
        yield db_session
    return _cm


async def _make_opp(db_session, ext="e1"):
    repo = OpportunityRepository(db_session)
    await repo.upsert_many([{"external_id": ext, "title": "Dev", "company": "Acme", "url": "https://x/1",
                             "description": "snippet"}])
    opps = await repo.get_all()
    return repo, [o for o in opps if o.external_id == ext][0].id


def _result(pdf: bytes = b"%PDF-1", name: str = "CV_Rudy.pdf") -> dict:
    return {
        "tailored_cv": {"full_name": "Rudy Botosso", "email": "r@x.it", "skills": ["Python"]},
        "cover_letter": {"subject": "s", "full_text": "t"},
        "draft_id": "d1", "gmail_url": "https://g/1",
        "advertiser_type": "recruiter", "contact_email": "a@b.it",
        "pdf_bytes": pdf, "pdf_filename": name,
    }


# -- record_draft --
async def test_record_draft_creates_application_and_document(db_session):
    cv_id = await _create_parsed_cv(db_session)
    _, oid = await _make_opp(db_session)
    rec = await oa.record_draft(db_session, oid, cv_id, _result(), "full job text")
    assert rec.opportunity_id == oid
    assert (rec.company, rec.role, rec.source_url) == ("Acme", "Dev", "https://x/1")
    assert rec.job_description == "full job text"
    assert rec.status == "ready" and rec.draft_status == "ready" and rec.cover_letter_status == "ready"
    assert rec.draft_url == "https://g/1"
    assert rec.advertiser_type == "recruiter" and rec.contact_email == "a@b.it"
    assert json.loads(rec.tailored_cv)["full_name"] == "Rudy Botosso"
    docs = await ApplicationRepository(db_session).list_documents(rec.id)
    assert len(docs) == 1 and docs[0].kind == "cv_su_misura" and docs[0].filename == "CV_Rudy.pdf"
    assert docs[0].size == 6


async def test_record_draft_reuses_application_and_adds_document(db_session):
    cv_id = await _create_parsed_cv(db_session)
    _, oid = await _make_opp(db_session)
    a = await oa.record_draft(db_session, oid, cv_id, _result(b"one", "a.pdf"), "t")
    b = await oa.record_draft(db_session, oid, cv_id, _result(b"two!", "b.pdf"), "t")
    assert a.id == b.id
    assert len(await ApplicationRepository(db_session).get_all()) == 1
    docs = await ApplicationRepository(db_session).list_documents(a.id)
    assert [d.filename for d in docs] == ["b.pdf", "a.pdf"]


async def test_record_draft_never_downgrades_status(db_session):
    cv_id = await _create_parsed_cv(db_session)
    _, oid = await _make_opp(db_session)
    a = await oa.record_draft(db_session, oid, cv_id, _result(), "t")
    await ApplicationRepository(db_session).update_status(a.id, "applied")
    b = await oa.record_draft(db_session, oid, cv_id, _result(), "t")
    assert b.status == "applied"


# -- mark_applied --
async def test_mark_applied_creates_application(db_session):
    cv_id = await _create_parsed_cv(db_session)
    orepo, oid = await _make_opp(db_session)
    rec = await oa.mark_applied(db_session, oid, cv_id)
    assert rec.status == "applied" and rec.applied_at is not None
    assert rec.opportunity_id == oid and rec.job_description == "snippet"
    assert [h["status"] for h in json.loads(rec.status_history)] == ["applied"]
    assert (await orepo.get_by_id(oid)).status == "applied"


async def test_mark_applied_idempotent_and_reuses(db_session):
    cv_id = await _create_parsed_cv(db_session)
    _, oid = await _make_opp(db_session)
    a = await oa.record_draft(db_session, oid, cv_id, _result(), "t")
    b = await oa.mark_applied(db_session, oid, cv_id)
    c = await oa.mark_applied(db_session, oid, cv_id)
    assert a.id == b.id == c.id
    hist = [h["status"] for h in json.loads(c.status_history)]
    assert hist == ["ready", "applied"]
    assert len(await ApplicationRepository(db_session).get_all()) == 1


async def test_mark_applied_unknown_opportunity(db_session):
    assert await oa.mark_applied(db_session, 999, 1) is None


# -- _run_create_draft --
_CV = {"full_name": "Rudy Botosso", "email": "r@x.it", "skills": ["Python"]}


async def test_run_create_draft_creates_application(db_session):
    cv_id = await _create_parsed_cv(db_session)
    _, oid = await _make_opp(db_session)
    with patch.object(market_ep, "AsyncSessionLocal", _factory(db_session)), \
         patch.object(market_ep, "build_tailored_draft", new=AsyncMock(return_value=_result())), \
         patch.object(market_ep, "resolve_job_text", new=AsyncMock(return_value=("full text", True))):
        out = await market_ep._run_create_draft(oid, _CV, "Dev", "Acme", "snippet", url="https://x/1", cv_id=cv_id)
    assert out is not None and out["registered"] is True
    rec = await ApplicationRepository(db_session).get_by_opportunity_id(oid)
    assert rec is not None and rec.job_description == "full text" and rec.cv_id == cv_id
    assert len(await ApplicationRepository(db_session).list_documents(rec.id)) == 1


async def test_run_create_draft_survives_record_failure(db_session):
    repo, oid = await _make_opp(db_session)
    with patch.object(market_ep, "AsyncSessionLocal", _factory(db_session)), \
         patch.object(market_ep, "build_tailored_draft", new=AsyncMock(return_value=_result())), \
         patch.object(market_ep, "resolve_job_text", new=AsyncMock(return_value=("t", False))), \
         patch.object(market_ep, "record_draft", new=AsyncMock(side_effect=ValueError("db"))):
        out = await market_ep._run_create_draft(oid, _CV, "Dev", "Acme", "snippet")
    assert out is not None and out["gmail_url"] == "https://g/1" and out["registered"] is False
    assert (await repo.get_by_id(oid)).draft_status == "ready"


# -- PATCH status --
async def test_patch_status_applied_triggers_mark_applied(client, db_session):
    await _create_parsed_cv(db_session)
    _, oid = await _make_opp(db_session)
    r = await client.patch(f"/api/v1/market/opportunities/{oid}/status", json={"status": "applied"})
    assert r.status_code == 200 and r.json()["status"] == "applied"
    rec = await ApplicationRepository(db_session).get_by_opportunity_id(oid)
    assert rec is not None and rec.status == "applied"


async def test_patch_status_saved_does_not_create_application(client, db_session):
    _, oid = await _make_opp(db_session)
    r = await client.patch(f"/api/v1/market/opportunities/{oid}/status", json={"status": "saved"})
    assert r.status_code == 200
    assert await ApplicationRepository(db_session).get_by_opportunity_id(oid) is None


async def test_patch_status_unknown_opp_404(client):
    r = await client.patch("/api/v1/market/opportunities/999/status", json={"status": "applied"})
    assert r.status_code == 404


# -- documents API --
async def test_documents_list_and_download(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    _, oid = await _make_opp(db_session)
    rec = await oa.record_draft(db_session, oid, cv_id, _result(b"%PDF-bytes", "CV_Rudy.pdf"), "t")
    r = await client.get(f"/api/v1/applications/{rec.id}/documents")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1 and items[0]["filename"] == "CV_Rudy.pdf" and items[0]["size"] == 10
    assert set(items[0]) >= {"id", "kind", "filename", "size", "created_at"}
    d = await client.get(f"/api/v1/applications/{rec.id}/documents/{items[0]['id']}")
    assert d.status_code == 200
    assert d.headers["content-type"].startswith("application/pdf")
    assert 'inline; filename="CV_Rudy.pdf"' in d.headers["content-disposition"]
    assert d.content == b"%PDF-bytes"
    detail = await client.get(f"/api/v1/applications/{rec.id}")
    assert detail.json()["documents"][0]["filename"] == "CV_Rudy.pdf"
    assert "content" not in detail.json()["documents"][0]


async def test_documents_404s(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    _, o1 = await _make_opp(db_session, "e1")
    _, o2 = await _make_opp(db_session, "e2")
    a = await oa.record_draft(db_session, o1, cv_id, _result(), "t")
    b = await oa.record_draft(db_session, o2, cv_id, _result(), "t")
    doc_a = (await ApplicationRepository(db_session).list_documents(a.id))[0]
    assert (await client.get("/api/v1/applications/999/documents")).status_code == 404
    assert (await client.get(f"/api/v1/applications/{a.id}/documents/9999")).status_code == 404
    assert (await client.get(f"/api/v1/applications/{b.id}/documents/{doc_a.id}")).status_code == 404
    assert (await client.get("/api/v1/applications/999/documents/1")).status_code == 404


async def test_delete_by_cv_removes_documents(db_session):
    cv_id = await _create_parsed_cv(db_session)
    _, oid = await _make_opp(db_session)
    rec = await oa.record_draft(db_session, oid, cv_id, _result(), "t")
    repo = ApplicationRepository(db_session)
    assert await repo.delete_by_cv_id(cv_id) == 1
    assert await repo.list_documents(rec.id) == []


# -- Telegram --
async def test_send_opportunity_has_applied_button():
    class Opp:
        id = 7
        url = "https://x"
        title = "T"
        company = "C"
        location = None
        salary_min = None
        salary_max = None
        source = "s"
        match_score = 80

    with patch.object(telegram_service, "_call", new=AsyncMock()) as call:
        await telegram_service.send_opportunity(Opp())
    kb = call.call_args.args[1]["reply_markup"]["inline_keyboard"]
    data = [b.get("callback_data") for row in kb for b in row]
    assert {"draft:7", "save:7", "dismiss:7", "applied:7"} <= set(data)


async def test_callback_applied_calls_mark_applied(db_session):
    cv_id = await _create_parsed_cv(db_session)
    await CVRepository(db_session).set_base(cv_id)
    with patch("app.core.database.AsyncSessionLocal", _factory(db_session)), \
         patch.object(oa, "mark_applied", new=AsyncMock(return_value=object())) as ma, \
         patch.object(telegram_service, "_answer_callback", new=AsyncMock()) as ans, \
         patch.object(telegram_service, "send_text", new=AsyncMock()) as st:
        await telegram_service._handle_callback({"id": "c1", "data": "applied:5"})
    assert ma.await_args.args[1:] == (5, cv_id)
    assert "Segnata" in ans.await_args.args[1]
    st.assert_awaited_once()


async def test_callback_applied_unknown_opportunity(db_session):
    await CVRepository(db_session).set_base(await _create_parsed_cv(db_session))
    with patch("app.core.database.AsyncSessionLocal", _factory(db_session)), \
         patch.object(oa, "mark_applied", new=AsyncMock(return_value=None)), \
         patch.object(telegram_service, "_answer_callback", new=AsyncMock()) as ans, \
         patch.object(telegram_service, "send_text", new=AsyncMock()):
        await telegram_service._handle_callback({"id": "c1", "data": "applied:5"})
    assert "⚠️" in ans.await_args.args[1]


def test_confirmation_mentions_candidature():
    t = telegram_service.format_draft_confirmation({"gmail_url": "u", "registered": True})
    assert t.splitlines()[-1] == "• Registrata in Candidature"


def test_confirmation_honest_when_not_registered():
    t = telegram_service.format_draft_confirmation({"gmail_url": "u"})
    assert t.splitlines()[-1] == "• Non registrata in Candidature (errore, vedi log)"
