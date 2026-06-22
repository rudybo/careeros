"""Unit tests for CVExpert guardrails — no Ollama required."""
import pytest

from app.agents.cv_expert.agent import _apply_guardrails, _format_cv_for_expert
from app.schemas.cv import Education, ParsedCV, WorkExperience


def _make_cv(skills: list[str], summary: str = "Dev") -> ParsedCV:
    return ParsedCV(
        full_name="Rudy Botosso",
        email="rudy@test.com",
        phone=None,
        summary=summary,
        skills=skills,
        languages=["Italiano"],
        work_experience=[
            WorkExperience(
                company="Acme",
                role="Backend Developer",
                start_date="2022",
                end_date=None,
                description="Built APIs with Python and FastAPI.",
            )
        ],
        education=[
            Education(institution="UniMi", degree="Bachelor", field="CS", year="2021")
        ],
        certifications=[],
    )


def _make_result(**overrides) -> dict:
    base = {
        "match_score": 70,
        "matched_keywords": ["Python", "FastAPI"],
        "missing_keywords": ["Docker", "Redis"],
        "ats_warnings": ["Missing Docker keyword"],
        "section_suggestions": [],
        "cover_letter_hints": ["hint1", "hint2", "hint3"],
        "optimized_summary": "Experienced developer.",
    }
    base.update(overrides)
    return base


JD = "We need a Python FastAPI Docker Redis expert with REST API experience."


# ─── matched_keywords validation ────────────────────────────────────────────

def test_matched_keywords_keeps_real_matches():
    cv = _make_cv(["Python", "FastAPI"])
    result = _apply_guardrails(_make_result(matched_keywords=["Python", "FastAPI"]), cv, JD)
    assert "Python" in result["matched_keywords"]
    assert "FastAPI" in result["matched_keywords"]


def test_matched_keywords_removes_fabricated():
    cv = _make_cv(["Python"])
    result = _apply_guardrails(_make_result(matched_keywords=["Python", "Kubernetes"]), cv, JD)
    assert "Python" in result["matched_keywords"]
    assert "Kubernetes" not in result["matched_keywords"]


def test_matched_keywords_case_insensitive():
    cv = _make_cv(["python"])
    result = _apply_guardrails(_make_result(matched_keywords=["Python"]), cv, JD)
    assert "Python" in result["matched_keywords"]


# ─── missing_keywords validation ─────────────────────────────────────────────

def test_missing_keywords_removes_existing_skills():
    cv = _make_cv(["Python", "FastAPI", "Docker"])
    result = _apply_guardrails(_make_result(missing_keywords=["Docker", "Redis"]), cv, JD)
    assert "Docker" not in result["missing_keywords"]
    assert "Redis" in result["missing_keywords"]


def test_missing_keywords_capped_at_8():
    cv = _make_cv([])
    many = [f"skill{i}" for i in range(15)]
    result = _apply_guardrails(_make_result(missing_keywords=many), cv, JD)
    assert len(result["missing_keywords"]) <= 8


# ─── match_score recalculation ───────────────────────────────────────────────

def test_match_score_recalculated():
    cv = _make_cv(["Python"])
    # "Kubernetes" is not anywhere in the CV (skills or experience description)
    result = _apply_guardrails(
        _make_result(matched_keywords=["Python", "Kubernetes"], missing_keywords=["Docker"]),
        cv,
        JD,
    )
    # Kubernetes removed (not in CV), 1 real match (Python), 1 missing (Docker) → 50%
    assert "Kubernetes" not in result["matched_keywords"]
    assert result["match_score"] == 50


def test_match_score_zero_when_no_keywords():
    cv = _make_cv([])
    result = _apply_guardrails(
        _make_result(matched_keywords=[], missing_keywords=[]),
        cv,
        JD,
    )
    # No keywords at all — score stays at whatever model said (no division)
    assert isinstance(result["match_score"], int)


# ─── language fixes ───────────────────────────────────────────────────────────

def test_language_fix_cursa_in_summary():
    cv = _make_cv(["Python"])
    result = _apply_guardrails(
        _make_result(optimized_summary="Si consiglia di cursa un corso online."),
        cv,
        JD,
    )
    assert "cursa" not in result["optimized_summary"]
    assert "corso" in result["optimized_summary"]


def test_language_fix_cursa_in_section_suggestions():
    cv = _make_cv(["Python"])
    result = _apply_guardrails(
        _make_result(section_suggestions=[
            {"section": "skills", "issue": "Manca Docker", "suggestion": "cursa un corso su Docker"}
        ]),
        cv,
        JD,
    )
    assert "cursa" not in result["section_suggestions"][0]["suggestion"]


# ─── cv context formatting ───────────────────────────────────────────────────

def test_format_cv_includes_skills():
    cv = _make_cv(["Python", "FastAPI", "SQL"])
    text = _format_cv_for_expert(cv)
    assert "Python" in text
    assert "FastAPI" in text


def test_format_cv_includes_experience():
    cv = _make_cv(["Python"])
    text = _format_cv_for_expert(cv)
    assert "Acme" in text
    assert "Backend Developer" in text
