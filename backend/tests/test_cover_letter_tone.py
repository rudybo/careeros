from app.agents.cover_letter.agent import _build_context
from app.schemas.cv import ParsedCV


def _cv() -> ParsedCV:
    return ParsedCV(full_name="Rudy Botosso", skills=["Python"])


def test_recruiter_context_has_recruiter_tone():
    ctx = _build_context(_cv(), "Acme", "Dev", "jd", None, advertiser_type="recruiter")
    assert "ADVERTISER: RECRUITER" in ctx


def test_direct_context_has_direct_tone():
    ctx = _build_context(_cv(), "Acme", "Dev", "jd", None, advertiser_type="direct")
    assert "ADVERTISER: DIRECT COMPANY" in ctx


def test_unknown_advertiser_adds_nothing():
    ctx = _build_context(_cv(), "Acme", "Dev", "jd", None)
    assert "ADVERTISER" not in ctx
