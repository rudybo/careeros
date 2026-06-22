from app.agents.career_strategist.agent import _apply_guardrails, _is_existing_skill, _normalize
from app.schemas.cv import ParsedCV


def _make_cv(skills: list[str], certifications: list[str] | None = None) -> ParsedCV:
    return ParsedCV(
        full_name="Rudy Botosso",
        skills=skills,
        certifications=certifications or [],
        work_experience=[],
        education=[],
        languages=[],
    )


def _make_result(gaps: list[dict], roadmap: list[dict] | None = None) -> dict:
    return {
        "executive_summary": "Test summary.",
        "target_roles": [],
        "skill_gaps": gaps,
        "roadmap": roadmap or [],
    }


# --- _normalize ---

def test_normalize_removes_punctuation():
    assert _normalize("Cyber Security!") == "cyber security"


def test_normalize_lowercases():
    assert _normalize("Cloud Computing") == "cloud computing"


# --- _is_existing_skill ---

def test_exact_match_detected():
    assert _is_existing_skill("Cyber Security", ["Cyber Security", "Python"]) is True


def test_case_insensitive_match():
    assert _is_existing_skill("cyber security", ["Cyber Security"]) is True


def test_substring_match():
    assert _is_existing_skill("Data BI", ["Data & BI"]) is True


def test_no_match_returns_false():
    assert _is_existing_skill("Cloud Computing", ["Python", "SAP"]) is False


# --- _apply_guardrails: skill gaps ---

def test_removes_gap_already_in_cv():
    cv = _make_cv(skills=["Cyber Security", "Python"])
    result = _make_result(gaps=[
        {"skill": "Cyber Security", "priority": "alta", "why_needed": "x", "how_to_acquire": "y", "estimated_time": "1w"},
        {"skill": "Cloud Computing", "priority": "alta", "why_needed": "x", "how_to_acquire": "y", "estimated_time": "1w"},
    ])
    out = _apply_guardrails(result, cv)
    skills = [g["skill"] for g in out["skill_gaps"]]
    assert "Cyber Security" not in skills
    assert "Cloud Computing" in skills


def test_keeps_all_gaps_when_none_overlap():
    cv = _make_cv(skills=["Python"])
    result = _make_result(gaps=[
        {"skill": "Azure", "priority": "alta", "why_needed": "x", "how_to_acquire": "y", "estimated_time": "1w"},
        {"skill": "ITIL", "priority": "media", "why_needed": "x", "how_to_acquire": "y", "estimated_time": "1w"},
    ])
    out = _apply_guardrails(result, cv)
    assert len(out["skill_gaps"]) == 2


# --- _apply_guardrails: roadmap deduplication ---

def test_removes_duplicate_roadmap_steps():
    cv = _make_cv(skills=[])
    result = _make_result(gaps=[], roadmap=[
        {"order": 1, "action": "completare corso Azure su Microsoft Learn", "category": "skill", "impact": "x", "timeframe": "y"},
        {"order": 2, "action": "completare corso Azure su Microsoft Learn oggi", "category": "skill", "impact": "x", "timeframe": "y"},
        {"order": 3, "action": "creare portfolio su GitHub", "category": "portfolio", "impact": "x", "timeframe": "y"},
    ])
    out = _apply_guardrails(result, cv)
    assert len(out["roadmap"]) == 2


def test_roadmap_renumbered_after_dedup():
    cv = _make_cv(skills=[])
    result = _make_result(gaps=[], roadmap=[
        {"order": 1, "action": "azione alpha unica nel suo genere", "category": "skill", "impact": "x", "timeframe": "y"},
        {"order": 2, "action": "azione alpha unica nel suo genere duplicata", "category": "skill", "impact": "x", "timeframe": "y"},
        {"order": 3, "action": "azione beta completamente diversa", "category": "network", "impact": "x", "timeframe": "y"},
    ])
    out = _apply_guardrails(result, cv)
    orders = [s["order"] for s in out["roadmap"]]
    assert orders == [1, 2]


# --- _apply_guardrails: language fixes ---

def test_fixes_cursa_to_corso():
    cv = _make_cv(skills=[])
    result = _make_result(gaps=[
        {"skill": "Azure", "priority": "alta", "why_needed": "x", "how_to_acquire": "cursa su Microsoft Learn", "estimated_time": "1w"},
    ])
    out = _apply_guardrails(result, cv)
    assert out["skill_gaps"][0]["how_to_acquire"] == "corso su Microsoft Learn"
