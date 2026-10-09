import difflib
import logging
import re
import unicodedata
from pathlib import Path

from pydantic import ValidationError

from app.core.json_utils import loads_llm_json
from app.core.llm import LLMError, chat
from app.schemas.cv import ParsedCV, WorkExperience

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")
_MAX_JOB_CHARS = 6000
_MAX_HIGHLIGHTS = 6
_FALLBACK_HIGHLIGHTS = 3
_SNAP_RATIO = 0.6
_MAX_PROJECTS = 2


class CVTailorError(Exception):
    pass


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _snap_key(s: str | None) -> str:
    flat = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", flat).strip(" .,;:!?-*\"'()[]")


def _snap(candidate: str | None, base_items: list[str], used: set[int] | None = None) -> str | None:
    """Testo del base più simile al candidato (ratio >= soglia), sempre verbatim; None se nessuno."""
    key = _snap_key(candidate)
    if not key:
        return None
    best_i, best_r = -1, 0.0
    for i, item in enumerate(base_items):
        r = difflib.SequenceMatcher(None, key, _snap_key(item)).ratio()
        if r > best_r:
            best_i, best_r = i, r
    if best_i < 0 or best_r < _SNAP_RATIO or (used is not None and best_i in used):
        return None
    if used is not None:
        used.add(best_i)
    return base_items[best_i]


def _filter_highlights(candidates: list[str], b: WorkExperience) -> list[str]:
    used: set[int] = set()
    kept: list[str] = []
    for h in candidates:
        snapped = _snap(h, b.highlights, used)
        if snapped is None:
            logger.warning("CV Tailor: highlight non presente nel base scartato (%s): %.80s", b.company, h)
            continue
        kept.append(snapped)
    kept = kept[:_MAX_HIGHLIGHTS]
    return kept or list(b.highlights[:_FALLBACK_HIGHLIGHTS])


def _filter_projects(candidates: list[str], base: ParsedCV) -> list[str]:
    used: set[int] = set()
    kept: list[str] = []
    for p in candidates:
        snapped = _snap(p, base.projects, used)
        if snapped is None:
            logger.warning("CV Tailor: progetto non presente nel base scartato: %.80s", p)
            continue
        kept.append(snapped)
    return kept[:_MAX_PROJECTS]


def _canonical(items: list[str], base_items: list[str]) -> list[str]:
    by_norm = {_norm(b): b for b in reversed(base_items)}
    out: list[str] = []
    for i in items:
        c = by_norm.get(_norm(i))
        if c is not None and c not in out:
            out.append(c)
    return out


def _find_base_exp(exp: WorkExperience, base: ParsedCV) -> WorkExperience | None:
    for b in base.work_experience:
        if _norm(b.company) == _norm(exp.company) and _norm(b.role) == _norm(exp.role):
            return b
    return None


def enforce_base_facts(tailored: ParsedCV, base: ParsedCV) -> ParsedCV:
    kept_by_key: dict[tuple[str, str], WorkExperience] = {}
    seen: set[tuple[str, str]] = set()
    for exp in tailored.work_experience:
        b = _find_base_exp(exp, base)
        key = (_norm(exp.company), _norm(exp.role))
        if b is None or key in seen:
            logger.warning("CV Tailor: esperienza non verificabile scartata: %s @ %s", exp.role, exp.company)
            continue
        seen.add(key)
        # Mai testo dell'LLM: la descrizione è quella del base oppure vuota (omessa).
        desc = b.description if (exp.description or "").strip() else None
        kept_by_key[(_norm(b.company), _norm(b.role))] = WorkExperience(
            company=b.company, role=b.role, start_date=b.start_date, end_date=b.end_date, description=desc,
            highlights=_filter_highlights(exp.highlights, b))
    if not kept_by_key:
        raise CVTailorError("Il CV adattato non contiene esperienze verificabili.")

    # Lo storico non si perde mai: tutte le esperienze del base, nell'ordine del base.
    exps: list[WorkExperience] = []
    for b in base.work_experience:
        kept = kept_by_key.get((_norm(b.company), _norm(b.role)))
        if kept is None:
            d = (b.description or "").strip()
            kept = WorkExperience(company=b.company, role=b.role, start_date=b.start_date, end_date=b.end_date,
                                  description=d if d and len(d) <= 120 and "\n" not in d else None)
        exps.append(kept)

    summary = base.summary if (tailored.summary or "").strip() else None

    # Lista vuota dall'LLM = progetti omessi di proposito (annuncio non tecnico) -> resta vuota.
    # Chiave "projects" assente dall'output -> fallback al primo progetto del base.
    if "projects" in tailored.model_fields_set:
        projects = _filter_projects(tailored.projects, base)
    else:
        projects = list(base.projects[:1])

    return ParsedCV(
        full_name=base.full_name, email=base.email, phone=base.phone, location=base.location,
        linkedin=base.linkedin,
        summary=summary,
        skills=_canonical(tailored.skills, base.skills),
        work_experience=exps,
        education=base.education,
        languages=base.languages,
        certifications=_canonical(tailored.certifications, base.certifications),
        projects=projects,
    )


async def tailor(base: ParsedCV, job_text: str) -> ParsedCV:
    user_message = (
        f"BASE CV (JSON):\n{base.model_dump_json(exclude_none=True, exclude_defaults=True)}\n\n"
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
