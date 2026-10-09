import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from sqlalchemy import text

from app.models.cv import CV
from app.repositories.application_repository import ApplicationRepository
from app.repositories.market_repository import OpportunityRepository
from app.services import gmail_service, sent_check, telegram_service
from app.services import opportunity_application as oa

SENT_MS = 1_750_000_000_000  # epoch ms
SENT_DT = datetime.fromtimestamp(SENT_MS / 1000, tz=timezone.utc)


def _http_error(status: int) -> HttpError:
    resp = MagicMock()
    resp.status = status
    resp.reason = "x"
    return HttpError(resp, b"x")


# -- _sent_time_from_thread --
def test_sent_time_draft_only_is_none():
    t = {"messages": [{"labelIds": ["DRAFT"], "internalDate": "1000"}]}
    assert gmail_service._sent_time_from_thread(t) is None


def test_sent_time_earliest_sent_utc_aware():
    t = {"messages": [
        {"labelIds": ["SENT"], "internalDate": str(SENT_MS + 5000)},
        {"labelIds": ["INBOX"], "internalDate": "1"},
        {"labelIds": ["SENT"], "internalDate": str(SENT_MS)},
    ]}
    res = gmail_service._sent_time_from_thread(t)
    assert res == SENT_DT and res.tzinfo is not None and res.utcoffset().total_seconds() == 0


def test_sent_time_ignores_draft_and_sent_together():
    t = {"messages": [{"labelIds": ["DRAFT", "SENT"], "internalDate": str(SENT_MS)}]}
    assert gmail_service._sent_time_from_thread(t) is None


@pytest.mark.parametrize("garbage", [None, {}, {"messages": None}, {"messages": ["x"]},
                                      {"messages": [{"labelIds": ["SENT"], "internalDate": "abc"}]},
                                      {"messages": [{"labelIds": ["SENT"]}]}, "zzz"])
def test_sent_time_garbage_is_none(garbage):
    assert gmail_service._sent_time_from_thread(garbage) is None


# -- thread_id_from_draft_url --
def test_thread_id_from_draft_url_parses():
    service = MagicMock()
    service.users().messages().get().execute.return_value = {"threadId": "T9"}
    assert gmail_service.thread_id_from_draft_url(service, "https://mail.google.com/mail/u/0/#drafts/M1") == "T9"
    assert service.users().messages().get.call_args.kwargs == {"userId": "me", "id": "M1", "format": "minimal"}


@pytest.mark.parametrize("url", ["https://mail.google.com/mail/u/0/#drafts", "https://mail.google.com/mail/u/0/#drafts/", "", None])
def test_thread_id_from_draft_url_without_id(url):
    service = MagicMock()
    assert gmail_service.thread_id_from_draft_url(service, url) is None
    service.users().messages().get.assert_not_called()


def test_thread_id_from_draft_url_404():
    service = MagicMock()
    service.users().messages().get().execute.side_effect = _http_error(404)
    assert gmail_service.thread_id_from_draft_url(service, "x/#drafts/M1") is None


def test_get_sent_time_uses_thread_and_404():
    service = MagicMock()
    service.users().threads().get().execute.return_value = {
        "messages": [{"labelIds": ["SENT"], "internalDate": str(SENT_MS)}]}
    assert gmail_service.get_sent_time(service, "T1") == SENT_DT
    assert service.users().threads().get.call_args.kwargs == {"userId": "me", "id": "T1", "format": "minimal"}
    service.users().threads().get().execute.side_effect = _http_error(404)
    assert gmail_service.get_sent_time(service, "T1") is None


def test_create_draft_returns_thread_id():
    service = MagicMock()
    service.users().labels().list().execute.return_value = {"labels": [{"name": "CareerOS", "id": "L1"}]}
    service.users().drafts().create().execute.return_value = {"id": "D1", "message": {"id": "M1", "threadId": "T1"}}
    with patch.object(gmail_service, "get_gmail_service", return_value=service):
        assert gmail_service.create_draft("", "o", "c")["thread_id"] == "T1"
    service.users().drafts().create().execute.return_value = {"id": "D1", "message": {"id": "M1"}}
    with patch.object(gmail_service, "get_gmail_service", return_value=service):
        assert gmail_service.create_draft("", "o", "c")["thread_id"] == ""


# -- storage --
async def _cv(db_session) -> int:
    cv = CV(filename="a.pdf", raw_text="x", status="parsed", parsed_data="{}")
    db_session.add(cv)
    await db_session.commit()
    await db_session.refresh(cv)
    return cv.id


async def _ready_app(db_session, thread_id=None, company="Acme", role="Dev", opp_id=None):
    repo = ApplicationRepository(db_session)
    cv_id = await _cv(db_session)
    if opp_id is None:
        a = await repo.create(cv_id, company, role, "jd")
    else:
        a = await repo.create_from_opportunity(cv_id, opp_id, company, role, "jd")
    await repo.update_draft(a.id, {"full_name": "R"}, {"subject": "s", "full_text": "t"},
                            "https://mail.google.com/mail/u/0/#drafts/M1", thread_id=thread_id)
    return await repo.update_status(a.id, "ready")


async def test_update_draft_stores_thread_id(db_session):
    a = await _ready_app(db_session, thread_id="T1")
    assert a.gmail_thread_id == "T1"
    a = await ApplicationRepository(db_session).update_draft(a.id, {}, {}, "u")
    assert a.gmail_thread_id == "T1"  # senza thread_id non lo cancella


async def test_record_draft_stores_thread_id(db_session):
    cv_id = await _cv(db_session)
    orepo = OpportunityRepository(db_session)
    await orepo.upsert_many([{"external_id": "e1", "title": "Dev", "company": "Acme", "url": "u", "description": "d"}])
    oid = (await orepo.get_all())[0].id
    result = {"tailored_cv": {"full_name": "R"}, "cover_letter": {"subject": "s", "full_text": "t"},
              "draft_id": "d", "gmail_url": "https://g/1", "thread_id": "T7",
              "advertiser_type": None, "contact_email": None, "pdf_bytes": b"x", "pdf_filename": "a.pdf"}
    rec = await oa.record_draft(db_session, oid, cv_id, result, "t")
    assert rec.gmail_thread_id == "T7"


def test_columns_and_migration_declared():
    from app.models.application import JobApplication
    cols = JobApplication.__table__.columns
    assert "gmail_thread_id" in cols and "sent_at" in cols
    import inspect
    from app.core import database
    src = inspect.getsource(database)
    assert '"gmail_thread_id"' in src and '"sent_at"' in src


# -- check_sent_applications --
def _patch_gmail(sent=SENT_DT, thread="T1", service_exc=None, sent_exc=None):
    gs = MagicMock()
    if service_exc:
        gs.get_gmail_service.side_effect = service_exc
    gs.thread_id_from_draft_url.return_value = thread
    if sent_exc:
        gs.get_sent_time.side_effect = sent_exc
    else:
        gs.get_sent_time.return_value = sent
    return patch.object(sent_check, "gmail_service", gs), gs


async def test_sent_marks_applied_with_real_time(db_session):
    orepo = OpportunityRepository(db_session)
    await orepo.upsert_many([{"external_id": "e1", "title": "Dev", "company": "Acme", "url": "u", "description": "d"}])
    oid = (await orepo.get_all())[0].id
    a = await _ready_app(db_session, thread_id="T1", opp_id=oid)
    p, _ = _patch_gmail()
    with p, patch.object(telegram_service, "send_text", new=AsyncMock()) as tg:
        out = await sent_check.check_sent_applications(db_session)
    assert [o["application_id"] for o in out] == [a.id]
    assert out[0]["company"] == "Acme" and out[0]["role"] == "Dev" and out[0]["sent_at"] == SENT_DT
    rec = await ApplicationRepository(db_session).get_by_id(a.id)
    assert rec.status == "applied"
    assert rec.sent_at.replace(tzinfo=timezone.utc) == SENT_DT
    assert rec.applied_at.replace(tzinfo=timezone.utc) == SENT_DT
    hist = json.loads(rec.status_history)
    assert hist[-1]["status"] == "applied" and hist[-1]["at"] == SENT_DT.isoformat()
    assert (await orepo.get_by_id(oid)).status == "applied"
    tg.assert_awaited_once()
    assert "Rilevato invio" in tg.call_args.args[0] and "Dev" in tg.call_args.args[0]


async def test_telegram_failure_does_not_break(db_session):
    a = await _ready_app(db_session, thread_id="T1")
    p, _ = _patch_gmail()
    with p, patch.object(telegram_service, "send_text", new=AsyncMock(side_effect=RuntimeError("tg"))):
        out = await sent_check.check_sent_applications(db_session)
    assert len(out) == 1
    assert (await ApplicationRepository(db_session).get_by_id(a.id)).status == "applied"


async def test_not_sent_changes_nothing(db_session):
    a = await _ready_app(db_session, thread_id="T1")
    p, _ = _patch_gmail(sent=None)
    with p, patch.object(telegram_service, "send_text", new=AsyncMock()) as tg:
        out = await sent_check.check_sent_applications(db_session)
    assert out == []
    rec = await ApplicationRepository(db_session).get_by_id(a.id)
    assert rec.status == "ready" and rec.sent_at is None and rec.applied_at is None
    tg.assert_not_awaited()


async def test_already_applied_not_examined(db_session):
    a = await _ready_app(db_session, thread_id="T1")
    await ApplicationRepository(db_session).update_status(a.id, "applied")
    p, gs = _patch_gmail()
    with p, patch.object(telegram_service, "send_text", new=AsyncMock()):
        out = await sent_check.check_sent_applications(db_session)
    assert out == []
    gs.get_sent_time.assert_not_called()


async def test_gmail_error_returns_empty(db_session):
    aid = (await _ready_app(db_session, thread_id="T1")).id
    for kw in ({"service_exc": RuntimeError("Gmail non autenticato")}, {"sent_exc": _http_error(500)}):
        p, _ = _patch_gmail(**kw)
        with p, patch.object(telegram_service, "send_text", new=AsyncMock()):
            assert await sent_check.check_sent_applications(db_session) == []
    rec = await ApplicationRepository(db_session).get_by_id(aid)
    assert rec.status == "ready" and rec.sent_at is None


async def test_derives_and_stores_thread_id(db_session):
    a = await _ready_app(db_session, thread_id=None)
    p, gs = _patch_gmail(sent=None, thread="TDER")
    with p:
        await sent_check.check_sent_applications(db_session)
    gs.thread_id_from_draft_url.assert_called_once()
    assert (await ApplicationRepository(db_session).get_by_id(a.id)).gmail_thread_id == "TDER"


async def test_restricted_to_app_id(db_session):
    a = await _ready_app(db_session, thread_id="T1")
    b = await _ready_app(db_session, thread_id="T2", company="B")
    p, gs = _patch_gmail()
    with p, patch.object(telegram_service, "send_text", new=AsyncMock()):
        out = await sent_check.check_sent_applications(db_session, app_id=b.id)
    assert [o["application_id"] for o in out] == [b.id]
    assert (await ApplicationRepository(db_session).get_by_id(a.id)).status == "ready"


# -- endpoints --
async def test_endpoint_check_sent_all(client, db_session):
    await _ready_app(db_session, thread_id="T1")
    res = [{"application_id": 1, "company": "A", "role": "R", "sent_at": SENT_DT}]
    with patch("app.api.v1.endpoints.application.check_sent_applications", new=AsyncMock(return_value=res)):
        r = await client.post("/api/v1/applications/check-sent")
    assert r.status_code == 200
    body = r.json()
    assert body["sent"][0]["application_id"] == 1 and body["sent"][0]["company"] == "A"
    assert body["checked"] == 1


async def test_endpoint_check_sent_one_and_404(client, db_session):
    assert (await client.post("/api/v1/applications/999/check-sent")).status_code == 404
    a = await _ready_app(db_session, thread_id="T1")
    with patch("app.api.v1.endpoints.application.check_sent_applications", new=AsyncMock(return_value=[])) as m:
        r = await client.post(f"/api/v1/applications/{a.id}/check-sent")
    assert r.status_code == 200 and r.json() == {"checked": 1, "sent": []}
    assert m.call_args.kwargs.get("app_id") == a.id or a.id in m.call_args.args


async def test_detail_exposes_sent_at(client, db_session):
    a = await _ready_app(db_session, thread_id="T1")
    r = await client.get(f"/api/v1/applications/{a.id}")
    assert "sent_at" in r.json() and r.json()["sent_at"] is None
