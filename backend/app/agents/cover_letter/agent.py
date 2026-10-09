import json
import logging
from pathlib import Path

from app.core.llm import chat, LLMError

from app.core.config import settings
from app.schemas.cv import ParsedCV
from app.schemas.application import CVOptimization

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompt.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

_MIN_LENGTH = 85  # minimo parole (cover letter ora sono brevi: target 110-160)

_TONE = {
    "recruiter": (
        "ADVERTISER: RECRUITER (recruiting agency, client company may be undisclosed). "
        "Write 100-130 words: focus on candidate profile, key skills, availability and notice period; "
        "do NOT praise the client company, do not assume you know it."
    ),
    "direct": (
        "ADVERTISER: DIRECT COMPANY (the company hiring directly). "
        "Write 120-160 words: be specific about why this company and this role, linking 1-2 concrete experiences."
    ),
}


class CoverLetterError(Exception):
    pass


def _build_context(cv: ParsedCV, company: str, role: str, job_description: str, optimization: CVOptimization | None, advertiser_type: str | None = None) -> str:
    lines = [
        f"CANDIDATE: {cv.full_name}",
        f"TARGET COMPANY: {company}",
        f"TARGET ROLE: {role}",
        "",
        f"SKILLS: {', '.join(cv.skills) if cv.skills else 'N/A'}",
        f"LANGUAGES: {', '.join(cv.languages) if cv.languages else 'N/A'}",
        "",
        "MOST RECENT EXPERIENCE:",
    ]
    for exp in cv.work_experience[:6]:
        lines.append(f"  - {exp.role or '?'} at {exp.company or '?'} ({exp.start_date or '?'} – {exp.end_date or 'presente'})")
        if exp.description:
            lines.append(f"    {exp.description[:300]}")

    if optimization:
        lines += [
            "",
            "KEY TALKING POINTS FOR THIS APPLICATION (use these as the backbone of the letter):",
        ]
        for i, hint in enumerate(optimization.cover_letter_hints, 1):
            lines.append(f"  {i}. {hint}")

        if optimization.matched_keywords:
            lines += ["", f"KEYWORDS ALREADY IN CV (use naturally): {', '.join(optimization.matched_keywords[:6])}"]

    if advertiser_type in _TONE:
        lines += ["", _TONE[advertiser_type]]

    lines += ["", "JOB DESCRIPTION (excerpt):", job_description[:800]]
    return "\n".join(lines)


def _apply_guardrails(result: dict, cv: ParsedCV, company: str, role: str) -> dict:
    full_text: str = result.get("full_text", "")

    # 1. Ensure minimum length
    if len(full_text.split()) < _MIN_LENGTH:
        logger.warning("Cover letter too short (%d words), flagging", len(full_text.split()))
        raise CoverLetterError(f"Lettera troppo breve ({len(full_text.split())} parole). Riprova.")

    # 2. Ensure candidate name is present
    name_parts = cv.full_name.split()
    if not any(part.lower() in full_text.lower() for part in name_parts if len(part) > 2):
        full_text += f"\n\nCordiali saluti,\n{cv.full_name}"
        logger.info("Cover letter: aggiunto nome candidato mancante")

    # 3. Ensure company name is present
    if company.lower() not in full_text.lower():
        logger.warning("Cover letter: nome azienda '%s' non trovato nel testo", company)

    # 4. Language fixes
    full_text = full_text.replace("cursa", "corso").replace("Cursa", "Corso")
    result["full_text"] = full_text

    # 5. Fix subject if missing role or name
    subject = result.get("subject", "")
    if not subject or role.lower() not in subject.lower():
        result["subject"] = f"Candidatura per il ruolo di {role} - {cv.full_name}"

    return result


async def generate(cv: ParsedCV, company: str, role: str, job_description: str, optimization: CVOptimization | None, advertiser_type: str | None = None) -> dict:
    context = _build_context(cv, company, role, job_description, optimization, advertiser_type)

    logger.info("Cover Letter Generator: avvio per %s → %s @ %s", cv.full_name, role, company)

    try:
        raw = await chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
    except LLMError as e:
        raise CoverLetterError(str(e)) from e

    try:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Cover Letter: output non JSON: %s", raw[:300])
        raise CoverLetterError(f"Output non valido dal modello: {e}") from e

    return _apply_guardrails(result, cv, company, role)
