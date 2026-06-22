import json
import logging
import re
from pathlib import Path

import ollama

from app.core.config import settings
from app.schemas.cv import ParsedCV

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# Certifications that are not professional IT credentials and should be
# excluded from the context passed to the model (avoids hallucinations).
_NON_IT_CERT_PATTERNS = [
    r"patente",
    r"automunito",
    r"driving",
    r"driver",
]


class CareerStrategistError(Exception):
    pass


def _normalize(text: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace for fuzzy comparison."""
    cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_existing_skill(gap_skill: str, cv_skills: list[str]) -> bool:
    """Return True if gap_skill overlaps significantly with any existing CV skill."""
    gap_norm = _normalize(gap_skill)
    for skill in cv_skills:
        skill_norm = _normalize(skill)
        # Exact match or one contains the other
        if gap_norm == skill_norm:
            return True
        if gap_norm in skill_norm or skill_norm in gap_norm:
            return True
    return False


def _is_non_it_certification(cert: str) -> bool:
    cert_lower = cert.lower()
    return any(re.search(p, cert_lower) for p in _NON_IT_CERT_PATTERNS)


def _apply_guardrails(result: dict, cv: ParsedCV) -> dict:
    """
    Post-processing layer applied after Ollama output.
    Removes hallucinations and enforces business rules that the model
    cannot reliably follow on its own.
    """
    cv_skills = cv.skills or []

    # 1. Remove skill gaps that overlap with existing CV skills
    original_gaps = result.get("skill_gaps", [])
    filtered_gaps = [
        gap for gap in original_gaps
        if not _is_existing_skill(gap.get("skill", ""), cv_skills)
    ]
    if len(filtered_gaps) < len(original_gaps):
        removed = [g["skill"] for g in original_gaps if g not in filtered_gaps]
        logger.info("Guardrails: rimossi %d gap già presenti nel CV: %s", len(removed), removed)
    result["skill_gaps"] = filtered_gaps

    # 2. Remove duplicate roadmap steps (same action paraphrased)
    seen_actions: set[str] = set()
    unique_steps = []
    for step in result.get("roadmap", []):
        action_norm = _normalize(step.get("action", ""))
        # Use first 25 chars as fingerprint to catch paraphrased duplicates
        fingerprint = action_norm[:25]
        if fingerprint not in seen_actions:
            seen_actions.add(fingerprint)
            unique_steps.append(step)
    # Re-number after deduplication
    for i, step in enumerate(unique_steps, start=1):
        step["order"] = i
    result["roadmap"] = unique_steps

    # 3. Fix common Italian language errors from the model
    _fix_language(result)

    return result


def _fix_language(result: dict) -> None:
    """Fix recurring model language errors in-place."""
    fixes = {"cursa": "corso", "Cursa": "Corso"}

    def fix_text(text: str) -> str:
        for wrong, correct in fixes.items():
            text = text.replace(wrong, correct)
        return text

    for gap in result.get("skill_gaps", []):
        for field in ("skill", "why_needed", "how_to_acquire"):
            if field in gap and isinstance(gap[field], str):
                gap[field] = fix_text(gap[field])

    for step in result.get("roadmap", []):
        for field in ("action", "impact"):
            if field in step and isinstance(step[field], str):
                step[field] = fix_text(step[field])

    if "executive_summary" in result and isinstance(result["executive_summary"], str):
        result["executive_summary"] = fix_text(result["executive_summary"])


def _format_cv_context(cv: ParsedCV) -> str:
    lines = [
        f"CANDIDATE NAME: {cv.full_name}",
        f"Location: {cv.location or 'N/A'}",
        f"Professional Summary: {cv.summary or 'N/A'}",
        "",
        "--- SKILLS ALREADY POSSESSED (do NOT list these as gaps) ---",
    ]

    if cv.skills:
        for skill in cv.skills:
            lines.append(f"  - {skill}")
    else:
        lines.append("  (none listed)")

    it_certs = [c for c in (cv.certifications or []) if not _is_non_it_certification(c)]
    lines += [
        "",
        f"Languages: {', '.join(cv.languages) if cv.languages else 'N/A'}",
        f"Certifications: {', '.join(it_certs) if it_certs else 'N/A'}",
        "",
        "--- WORK EXPERIENCE ---",
    ]

    for exp in cv.work_experience:
        role = exp.role or "Unknown role"
        company = exp.company or "Unknown company"
        period = f"{exp.start_date or '?'} - {exp.end_date or 'present'}"
        lines.append(f"  - {role} at {company} ({period})")
        if exp.description:
            lines.append(f"    {exp.description[:400]}")

    lines += ["", "--- EDUCATION ---"]
    for edu in cv.education:
        lines.append(
            f"  - {edu.degree or '?'} in {edu.field or '?'} "
            f"at {edu.institution or '?'} ({edu.year or '?'})"
        )

    return "\n".join(lines)


async def analyze(cv: ParsedCV) -> dict:
    client = ollama.AsyncClient(host=settings.ollama_base_url)
    context = _format_cv_context(cv)

    logger.info("Career Strategist: avvio analisi per %s", cv.full_name)

    try:
        response = await client.chat(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Professional profile to analyze:\n\n{context}"},
            ],
            options={"temperature": 0.2, "num_predict": 2048},
        )
    except Exception as e:
        raise CareerStrategistError(f"Ollama non raggiungibile: {e}") from e

    raw = response.message.content.strip()

    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Career Strategist: risposta non JSON valida: %s", raw[:500])
        raise CareerStrategistError(f"Output non valido dal modello: {e}") from e

    return _apply_guardrails(result, cv)
