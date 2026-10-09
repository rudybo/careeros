import difflib
import logging
import re
import unicodedata
from pathlib import Path
from typing import Literal

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


_COMPLIANCE_KW = ("gdpr", "dpo", "privacy", "data protection", "industria 4.0", "industry 4.0", "compliance",
                  "asseverazione", "crediti d'imposta", "nis2", "iso 27001")
_IT_KW = ("sviluppat", "software", "sistemist", "infrastruttur", "erp", "network", "cloud", "python", "java",
          "sql", "devops", "helpdesk", "it manager", "business intelligence", "data warehouse", "cyber")
_ROLE_CONSULTING_RE = re.compile(r"consulente|dpo|data protection|privacy")
_TITLE_COMPLIANCE_RE = re.compile(
    r"dpo|gdpr|privacy|data protection|compliance|consulente privacy|responsabile protezione dati")


class CVTailorError(Exception):
    pass


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _fold(s: str | None) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def is_consulting(exp: WorkExperience) -> bool:
    """Euristica deterministica: esperienza di consulenza/compliance se il ruolo contiene
    consulente|dpo|data protection|privacy, oppure se piu' della meta' degli highlight contiene
    una parola chiave di compliance. Il nome dell'azienda non decide mai."""
    if _ROLE_CONSULTING_RE.search(_fold(exp.role)):
        return True
    hl = [_fold(h) for h in exp.highlights]
    hits = sum(1 for h in hl if any(k in h for k in _COMPLIANCE_KW))
    return bool(hl) and hits * 2 > len(hl)


def detect_focus(job_text: str) -> Literal["it", "compliance"]:
    """'compliance' se il titolo (prima riga) e' di privacy/DPO/compliance, oppure se nel testo le
    parole chiave di compliance sono >= 3 e piu' numerose di quelle IT; altrimenti 'it'."""
    text = _fold(job_text)
    if not text.strip():
        return "it"
    if _TITLE_COMPLIANCE_RE.search(text.split(chr(10), 1)[0]):
        return "compliance"
    comp = sum(text.count(k) for k in _COMPLIANCE_KW)
    it = sum(text.count(k) for k in _IT_KW)
    return "compliance" if comp >= 3 and comp > it else "it"


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


def enforce_base_facts(tailored: ParsedCV, base: ParsedCV,
                       focus: Literal["it", "compliance"] = "it") -> ParsedCV:
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

    # Solo collocazione: consulenza/compliance vs IT (classificate sull'esperienza del base).
    consulting = [e for e, b in zip(exps, base.work_experience) if is_consulting(b)]
    others = [e for e, b in zip(exps, base.work_experience) if not is_consulting(b)]
    main, secondary = (others, consulting) if focus == "it" else (consulting, others)
    if not main:
        main, secondary = exps, []

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
        work_experience=main,
        other_experience=secondary,
        education=base.education,
        languages=base.languages,
        certifications=_canonical(tailored.certifications, base.certifications),
        projects=projects,
    )


_NORMATIVE_TERMS = ("GDPR", "NIS2", "ISO 27001", "AI Act", "Industria 4.0", "Industry 4.0", "DPO", "ERP", "CRM",
                    "BI", "Business Intelligence", "Data Warehouse", "Power BI", "SQL Server", "Python")
_MAX_KEYWORDS = 12


def _word_re(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)


def _base_text(base: ParsedCV) -> str:
    parts = [base.summary or "", *base.skills, *base.certifications, *base.projects]
    for e in (*base.work_experience, *base.other_experience):
        parts += [e.role or "", e.description or "", *e.highlights]
    return _fold(" ".join(parts))


def extract_keywords(base: ParsedCV, job_text: str) -> list[str]:
    """Termini del CV base (skill, certificazioni, sigle note presenti nel base) che compaiono nell'annuncio."""
    base_text = _base_text(base)
    vocab = [t.strip() for t in (*base.skills, *base.certifications)]
    vocab += [t for t in _NORMATIVE_TERMS if _word_re(_fold(t)).search(base_text)]
    job = _fold(job_text)
    found: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for term in vocab:
        key = _fold(term)
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        m = _word_re(key).search(job)
        if m:
            found.append((m.start(), m.end(), term))
    # Scarta i termini il cui match cade dentro quello di un termine piu' lungo (es. "BI" in "Power BI").
    found = [f for f in found if not any(o is not f and o[0] <= f[0] and f[1] <= o[1] and (o[1] - o[0]) > (f[1] - f[0])
                                         for o in found)]
    found.sort(key=lambda x: x[0])
    return [t for _, _, t in found[:_MAX_KEYWORDS]]


async def tailor(base: ParsedCV, job_text: str) -> ParsedCV:
    user_message = (
        f"BASE CV (JSON):\n{base.model_dump_json(exclude_none=True, exclude_defaults=True)}\n\n"
        f"JOB POSTING:\n{job_text[:_MAX_JOB_CHARS]}"
    )
    focus = detect_focus(job_text)
    logger.info("CV Tailor: avvio per %s — annuncio %d chars, focus=%s", base.full_name, len(job_text), focus)
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
    out = enforce_base_facts(tailored, base, focus)
    out.keywords = extract_keywords(base, job_text[:_MAX_JOB_CHARS])
    return out
