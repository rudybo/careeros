from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from app.api.v1.endpoints import market as market_ep
from app.repositories.market_repository import OpportunityRepository
from app.services import application_draft
from app.services.job_fetcher import JobFetchError
from app.services.telegram_service import format_draft_confirmation


def _factory(db_session):
    @asynccontextmanager
    async def _cm():
        yield db_session
    return _cm


async def _make_opp(db_session, ext="e1"):
    repo = OpportunityRepository(db_session)
    await repo.upsert_many([{"external_id": ext, "title": "Dev", "company": "Acme", "url": "https://x/1",
                             "description": "snippet"}])
    return repo, (await repo.get_all())[0].id


# ── resolve_job_text ──
async def test_resolve_uses_full_text_when_longer():
    with patch.object(application_draft, "fetch_job_posting", new=AsyncMock(return_value="long full posting text")):
        assert await application_draft.resolve_job_text("https://x", "short") == ("long full posting text", True)


async def test_resolve_fallback_on_error():
    with patch.object(application_draft, "fetch_job_posting", new=AsyncMock(side_effect=JobFetchError("no"))):
        assert await application_draft.resolve_job_text("https://x", "short") == ("short", False)


async def test_resolve_fallback_when_shorter():
    with patch.object(application_draft, "fetch_job_posting", new=AsyncMock(return_value="tiny")):
        assert await application_draft.resolve_job_text("https://x", "a longer fallback") == ("a longer fallback", False)


async def test_resolve_none_url_no_fetch():
    with patch.object(application_draft, "fetch_job_posting", new=AsyncMock()) as f:
        assert await application_draft.resolve_job_text(None, "fb") == ("fb", False)
        assert await application_draft.resolve_job_text("", "fb") == ("fb", False)
    f.assert_not_called()


# ── update_draft ──
async def test_update_draft_stores_advertiser_type(db_session):
    repo, oid = await _make_opp(db_session)
    opp = await repo.update_draft(oid, "d1", "https://g/1", advertiser_type="recruiter")
    assert opp.advertiser_type == "recruiter" and opp.draft_status == "ready"


async def test_update_draft_three_args_keeps_none_and_existing(db_session):
    repo, oid = await _make_opp(db_session)
    opp = await repo.update_draft(oid, "d1", "https://g/1")
    assert opp.advertiser_type is None
    await repo.update_draft(oid, "d1", "https://g/1", advertiser_type="direct")
    opp = await repo.update_draft(oid, "d2", "https://g/2")
    assert opp.advertiser_type == "direct"


# ── _run_create_draft ──
_CV = {"full_name": "Rudy Botosso", "email": "r@x.it", "skills": ["Python"]}


async def test_run_create_draft_success(db_session):
    repo, oid = await _make_opp(db_session)
    res = {"draft_id": "d1", "gmail_url": "https://g/1", "advertiser_type": "recruiter", "contact_email": "a@b.it"}
    build = AsyncMock(return_value=res)
    with patch.object(market_ep, "AsyncSessionLocal", _factory(db_session)), \
         patch.object(market_ep, "build_tailored_draft", new=build), \
         patch.object(market_ep, "resolve_job_text", new=AsyncMock(return_value=("full", True))):
        out = await market_ep._run_create_draft(oid, _CV, "Dev", "Acme", "snippet", url="https://x/1")
    assert out == {**res, "used_full_posting": True, "registered": False}
    assert build.call_args.args[3] == "full"
    opp = await repo.get_by_id(oid)
    assert opp.draft_status == "ready" and opp.advertiser_type == "recruiter" and opp.gmail_url == "https://g/1"


async def test_run_create_draft_failure(db_session):
    repo, oid = await _make_opp(db_session)
    with patch.object(market_ep, "AsyncSessionLocal", _factory(db_session)), \
         patch.object(market_ep, "build_tailored_draft", new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch.object(market_ep, "resolve_job_text", new=AsyncMock(return_value=("s", False))):
        out = await market_ep._run_create_draft(oid, _CV, "Dev", "Acme", "snippet")
    assert out is None
    assert (await repo.get_by_id(oid)).draft_status == "none"


# ── format_draft_confirmation ──
def _res(**kw):
    base = {"gmail_url": "https://g/1", "advertiser_type": "recruiter", "contact_email": "a@b.it",
            "used_full_posting": True}
    base.update(kw)
    return base


def test_format_advertiser_variants():
    assert "Inserzionista: Recruiter" in format_draft_confirmation(_res(advertiser_type="recruiter"))
    assert "Inserzionista: Azienda diretta" in format_draft_confirmation(_res(advertiser_type="direct"))
    assert "Inserzionista: non rilevato" in format_draft_confirmation(_res(advertiser_type=None))


def test_format_email_and_posting():
    t = format_draft_confirmation(_res())
    assert t.startswith("✅ Bozza pronta su Gmail:\nhttps://g/1")
    assert "Destinatario: a@b.it" in t and "CV su misura allegato (PDF)" in t
    assert "Annuncio: completo dal link" in t
    t2 = format_draft_confirmation(_res(contact_email=None, used_full_posting=False))
    assert "Destinatario: non trovato (da inserire a mano)" in t2
    assert "Annuncio: estratto della ricerca" in t2


def test_format_escapes_html():
    t = format_draft_confirmation(_res(contact_email="a<b>&c@x.it", gmail_url="https://g/?a=1&b=2"))
    assert "a&lt;b&gt;&amp;c@x.it" in t and "a=1&amp;b=2" in t and "<b>" not in t


# ── API response ──
async def test_opportunity_response_has_advertiser_type(client, db_session):
    repo, oid = await _make_opp(db_session)
    await repo.update_draft(oid, "d1", "https://g/1", advertiser_type="direct")
    r = await client.get("/api/v1/market/opportunities")
    assert r.status_code == 200
    assert r.json()[0]["advertiser_type"] == "direct"
