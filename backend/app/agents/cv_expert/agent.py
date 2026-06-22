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


class CVExpertError(Exception):
    pass


def _format_cv_for_expert(cv: ParsedCV) -> str:
    lines = [
        f"CANDIDATE: {cv.full_name}",
        f"Summary: {cv.summary or 'N/A'}",
        "",
        f"Skills: {', '.join(cv.skills) if cv.skills else 'N/A'}",
        f"Languages: {', '.join(cv.languages) if cv.languages else 'N/A'}",
        "",
        "Work Experience:",
    ]
    for exp in cv.work_experience:
        role = exp.role or "N/A"
        company = exp.company or "N/A"
        period = f"{exp.start_date or '?'} - {exp.end_date or 'present'}"
        lines.append(f"  - {role} at {company} ({period})")
        if exp.description:
            lines.append(f"    {exp.description[:500]}")

    lines += ["", "Education:"]
    for edu in cv.education:
        lines.append(
            f"  - {edu.degree or '?'} in {edu.field or '?'} "
            f"at {edu.institution or '?'} ({edu.year or '?'})"
        )
    return "\n".join(lines)


def _apply_guardrails(result: dict, cv: ParsedCV, job_description: str) -> dict:
    jd_lower = job_description.lower()
    cv_text = _format_cv_for_expert(cv).lower()

    # 1. Validate matched_keywords — remove any that don't actually appear in CV text
    genuine_matches = [
        kw for kw in result.get("matched_keywords", [])
        if kw.lower() in cv_text
    ]
    removed = len(result.get("matched_keywords", [])) - len(genuine_matches)
    if removed:
        logger.info("CVExpert guardrails: rimossi %d matched_keywords non reali", removed)
    result["matched_keywords"] = genuine_matches

    # 2. Validate missing_keywords — remove any that are already in the CV
    genuine_missing = [
        kw for kw in result.get("missing_keywords", [])
        if kw.lower() not in cv_text
    ]
    result["missing_keywords"] = genuine_missing[:8]

    # 3. Recalculate match_score based on actual keyword overlap
    total_keywords = len(genuine_matches) + len(genuine_missing)
    if total_keywords > 0:
        result["match_score"] = round((len(genuine_matches) / total_keywords) * 100)

    # 4. Fix language errors
    for key in ("optimized_summary",):
        if key in result and isinstance(result[key], str):
            result[key] = result[key].replace("cursa", "corso").replace("Cursa", "Corso")

    for suggestion in result.get("section_suggestions", []):
        for field in ("issue", "suggestion"):
            if isinstance(suggestion.get(field), str):
                suggestion[field] = suggestion[field].replace("cursa", "corso")

    return result


async def analyze(cv: ParsedCV, job_description: str) -> dict:
    client = ollama.AsyncClient(host=settings.ollama_base_url)
    cv_context = _format_cv_for_expert(cv)

    logger.info("CV Expert: avvio analisi per %s — JD: %d chars", cv.full_name, len(job_description))

    user_message = (
        f"CV PROFILE:\n{cv_context}\n\n"
        f"JOB DESCRIPTION:\n{job_description}"
    )

    try:
        response = await client.chat(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            options={"temperature": 0.1, "num_predict": 2048},
        )
    except Exception as e:
        raise CVExpertError(f"Ollama non raggiungibile: {e}") from e

    raw = response.message.content.strip()

    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("CV Expert: risposta non JSON valida: %s", raw[:500])
        raise CVExpertError(f"Output non valido dal modello: {e}") from e

    return _apply_guardrails(result, cv, job_description)
