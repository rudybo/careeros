import logging
import re
from pathlib import Path

from pydantic import ValidationError

from app.core.json_utils import loads_llm_json
from app.core.llm import LLMError, chat
from app.schemas.cv import ParsedCV, WorkExperience

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")
_MAX_JOB_CHARS = 6000
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.\-]*[A-Za-z0-9+#]|[A-Za-z0-9]")


class CVTailorError(Exception):
    pass


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _cv_text(cv: ParsedCV) -> str:
    parts = [cv.summary or "", *cv.skills, *cv.certifications]
    for e in cv.work_experience:
        parts += [e.company or "", e.role or "", e.description or ""]
    return _norm(" ".join(parts))


def _tech_tokens(text: str) -> set[str]:
    """Token 'tecnici': maiuscola non iniziale di frase, cifre/#/+/., sigle maiuscole."""
    tokens: set[str] = set()
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        before = text[: m.start()].rstrip()
        sentence_start = not before or before[-1] in ".!?:\n•-*"
        has_inner_upper = any(c.isupper() for c in tok[1:])
        has_symbol_digit = any(c.isdigit() or c in "+#." for c in tok)
        is_acronym = len(tok) >= 2 and tok.isupper()
        capitalized_mid = tok[0].isupper() and not sentence_start
        if has_inner_upper or has_symbol_digit or is_acronym or capitalized_mid:
            tokens.add(tok.lower().rstrip("."))
    return tokens


def _base_tokens(base_text: str) -> set[str]:
    return {m.group(0).lower().rstrip(".") for m in _TOKEN_RE.finditer(base_text)}


def _is_clean(candidate: str | None, base_tokens: set[str]) -> bool:
    return _tech_tokens(candidate or "") <= base_tokens


def _find_base_exp(exp: WorkExperience, base: ParsedCV) -> WorkExperience | None:
    for b in base.work_experience:
        if _norm(b.company) == _norm(exp.company) and _norm(b.role) == _norm(exp.role):
            return b
    return None


def enforce_base_facts(tailored: ParsedCV, base: ParsedCV) -> ParsedCV:
    base_tokens = _base_tokens(_cv_text(base))

    exps: list[WorkExperience] = []
    seen: set[tuple[str, str]] = set()
    for exp in tailored.work_experience:
        b = _find_base_exp(exp, base)
        key = (_norm(exp.company), _norm(exp.role))
        if b is None or key in seen:
            logger.warning("CV Tailor: esperienza non verificabile scartata: %s @ %s", exp.role, exp.company)
            continue
        seen.add(key)
        desc = exp.description if _is_clean(exp.description, base_tokens) else b.description
        if desc != exp.description:
            logger.warning("CV Tailor: descrizione con tecnologie non presenti nel base, uso quella originale (%s)", b.company)
        exps.append(WorkExperience(company=b.company, role=b.role, start_date=b.start_date,
                                   end_date=b.end_date, description=desc))
    if not exps:
        raise CVTailorError("Il CV adattato non contiene esperienze verificabili.")

    base_skills = {_norm(s) for s in base.skills}
    base_certs = {_norm(c) for c in base.certifications}
    summary = tailored.summary if _is_clean(tailored.summary, base_tokens) else base.summary

    return ParsedCV(
        full_name=base.full_name, email=base.email, phone=base.phone, location=base.location,
        summary=summary,
        skills=[s for s in tailored.skills if _norm(s) in base_skills],
        work_experience=exps,
        education=base.education,
        languages=base.languages,
        certifications=[c for c in tailored.certifications if _norm(c) in base_certs],
    )


async def tailor(base: ParsedCV, job_text: str) -> ParsedCV:
    user_message = (
        f"BASE CV (JSON):\n{base.model_dump_json(exclude_none=True)}\n\n"
        f"JOB POSTING:\n{job_text[:_MAX_JOB_CHARS]}"
    )
    logger.info("CV Tailor: avvio per %s — annuncio %d chars", base.full_name, len(job_text))
    try:
        raw = await chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=3500,
        )
    except LLMError as e:
        raise CVTailorError(str(e)) from e
    try:
        tailored = ParsedCV(**loads_llm_json(raw))
    except (ValueError, ValidationError, TypeError) as e:
        logger.error("CV Tailor: output non valido: %s", raw[:500])
        raise CVTailorError(f"Output non valido dal modello: {e}") from e
    return enforce_base_facts(tailored, base)
