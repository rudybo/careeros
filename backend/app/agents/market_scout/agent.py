import json
import logging
from pathlib import Path

import httpx
from app.core.llm import chat

from app.core.config import settings
from app.schemas.cv import ParsedCV
from app.models.market import UserPreferences

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")
_ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/it/search"
_JOOBLE_BASE = "https://it.jooble.org/api"

_STRIP_SUFFIXES = {
    "europa", "europe", "italia", "italy", "group", "nord", "nord-ovest",
    "nordovest", "sud", "est", "ovest", "emea", "apac", "international",
}

# Default roles when no target_roles are set in preferences
_DEFAULT_ROLES = ["IT Manager", "Project Manager IT", "Service Manager IT"]

# Indizi testuali di lavoro da remoto (per dare priorità nel pool nazionale)
_REMOTE_HINTS = ("remot", "smart working", "telelavoro", "full remote", "da remoto", "100% remoto")


def _location_pref(prefs: UserPreferences | None) -> tuple[str | None, int | None]:
    """Città e raggio (km) dalle preferenze. None se città non impostata."""
    if prefs and prefs.city:
        return prefs.city.strip(), (prefs.radius_km or 50)
    return None, None


def _remote_likely(o: dict) -> bool:
    text = f"{o.get('title', '')} {o.get('description', '')}".lower()
    return any(h in text for h in _REMOTE_HINTS)


class ScoutError(Exception):
    pass


def _clean_role(role: str) -> str:
    words = role.split()
    cleaned = [w for w in words if w.lower() not in _STRIP_SUFFIXES]
    return " ".join(cleaned).strip() or role


def _get_search_roles(cv: ParsedCV, prefs: UserPreferences | None) -> list[str]:
    """Return the list of role keywords to search for."""
    if prefs and prefs.target_roles:
        roles = json.loads(prefs.target_roles) if isinstance(prefs.target_roles, str) else prefs.target_roles
        if roles:
            return roles
    # Fallback: derive from CV + defaults
    cv_roles = [_clean_role(e.role) for e in cv.work_experience[:2] if e.role]
    combined = list(dict.fromkeys(cv_roles + _DEFAULT_ROLES))  # deduplicate preserving order
    return combined[:5]


# ── Adzuna ────────────────────────────────────────────────────────────────────

async def _fetch_adzuna(params: dict) -> list[dict]:
    base = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{_ADZUNA_BASE}/1", params={**base, **params})
        resp.raise_for_status()
        return resp.json().get("results", [])


def _parse_adzuna(raw: dict) -> dict:
    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")
    if salary_min and salary_min < 20000:
        salary_min *= 12
    if salary_max and salary_max < 20000:
        salary_max *= 12
    return {
        "external_id": f"adzuna_{raw.get('id', '')}",
        "source": "adzuna",
        "title": raw.get("title", ""),
        "company": raw.get("company", {}).get("display_name"),
        "location": raw.get("location", {}).get("display_name"),
        "url": raw.get("redirect_url", ""),
        "description": raw.get("description", "")[:2000],
        "salary_min": salary_min,
        "salary_max": salary_max,
        "work_mode": None,
        "match_score": None,
        "match_reasons": None,
        "status": "new",
    }


async def _search_adzuna(
    roles: list[str],
    salary_min: int | None,
    where: str | None = None,
    distance: int | None = None,
) -> list[dict]:
    results = []
    seen: set[str] = set()
    for role in roles:
        try:
            params = {"what": role, "results_per_page": 10, "sort_by": "date"}
            if salary_min:
                params["salary_min"] = salary_min
            if where:
                params["where"] = where
                if distance:
                    params["distance"] = distance  # raggio in km dalla città
            raw_list = await _fetch_adzuna(params)
            for r in raw_list:
                parsed = _parse_adzuna(r)
                if parsed["external_id"] not in seen:
                    seen.add(parsed["external_id"])
                    results.append(parsed)
        except Exception as e:
            logger.warning("Adzuna query '%s' fallita: %s", role, e)
    return results


# ── Jooble ────────────────────────────────────────────────────────────────────

async def _search_jooble(
    roles: list[str],
    location: str = "Italia",
    radius: int | None = None,
) -> list[dict]:
    if not settings.jooble_api_key:
        return []
    results = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=20) as client:
        for role in roles:
            try:
                body = {"keywords": role, "location": location, "page": 1, "ResultOnPage": 10}
                if radius:
                    body["radius"] = str(radius)  # raggio in km dalla località
                resp = await client.post(
                    f"{_JOOBLE_BASE}/{settings.jooble_api_key}",
                    json=body,
                )
                resp.raise_for_status()
                jobs = resp.json().get("jobs", [])
                for j in jobs:
                    parsed = _parse_jooble(j)
                    if parsed["external_id"] not in seen:
                        seen.add(parsed["external_id"])
                        results.append(parsed)
            except Exception as e:
                logger.warning("Jooble query '%s' fallita: %s", role, e)
    return results


def _parse_jooble(raw: dict) -> dict:
    salary_text = raw.get("salary", "") or ""
    return {
        "external_id": f"jooble_{raw.get('id', raw.get('link', ''))}",
        "source": "jooble",
        "title": raw.get("title", ""),
        "company": raw.get("company") or None,
        "location": raw.get("location") or None,
        "url": raw.get("link", ""),
        "description": (raw.get("snippet", ""))[:2000],
        "salary_min": None,
        "salary_max": None,
        "work_mode": None,
        "match_score": None,
        "match_reasons": None,
        "status": "new",
    }


# ── Ranking ───────────────────────────────────────────────────────────────────

def _build_candidate_context(cv: ParsedCV, prefs: UserPreferences | None) -> str:
    lines = [
        f"CANDIDATE: {cv.full_name}",
        f"SKILLS: {', '.join(cv.skills[:10]) if cv.skills else 'N/A'}",
        f"LANGUAGES: {', '.join(cv.languages) if cv.languages else 'N/A'}",
    ]
    for e in cv.work_experience[:2]:
        lines.append(f"  - {e.role or '?'} @ {e.company or '?'} ({e.start_date or '?'} – {e.end_date or 'presente'})")
    if prefs:
        pref_lines = []
        if prefs.ral_min or prefs.ral_max:
            pref_lines.append(f"RAL: {prefs.ral_min or '?'}–{prefs.ral_max or '?'} €")
        if prefs.work_mode:
            pref_lines.append(f"Work mode: {prefs.work_mode}")
        if prefs.city:
            pref_lines.append(f"City: {prefs.city}")
        target = prefs.target_roles
        if target and isinstance(target, str):
            target = json.loads(target)
        if target:
            pref_lines.append(f"Open roles: {', '.join(target)}")
        if pref_lines:
            lines.append("PREFERENCES: " + " | ".join(pref_lines))
    return "\n".join(lines)


async def _rank_opportunity(candidate_ctx: str, opp: dict) -> dict:
    job_text = (
        f"TITLE: {opp['title']}\n"
        f"COMPANY: {opp['company'] or 'N/A'}\n"
        f"LOCATION: {opp['location'] or 'N/A'}\n"
        f"SALARY: {opp['salary_min'] or '?'}–{opp['salary_max'] or '?'} €/anno\n"
        f"DESCRIPTION: {opp['description'] or 'N/A'}"
    )
    try:
        raw = await chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"{candidate_ctx}\n\nJOB LISTING:\n{job_text}"},
            ],
            temperature=0.1,
            max_tokens=256,
        )
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        opp["match_score"] = max(0, min(100, int(result.get("match_score", 0))))
        opp["match_reasons"] = json.dumps(result.get("match_reasons", []), ensure_ascii=False)
        if result.get("work_mode") and result["work_mode"] != "unknown":
            opp["work_mode"] = result["work_mode"]
    except Exception as e:
        logger.warning("Ranking fallito per '%s': %s", opp.get("title"), e)
        opp["match_score"] = 0
        opp["match_reasons"] = json.dumps(["Valutazione non disponibile"], ensure_ascii=False)
    return opp


# ── Main search ───────────────────────────────────────────────────────────────

def _priority(o: dict) -> int:
    return (1 if o.get("description") else 0) + (1 if o.get("salary_min") or o.get("salary_max") else 0)


async def search(cv: ParsedCV, prefs: UserPreferences | None) -> list[dict]:
    roles = _get_search_roles(cv, prefs)
    salary_min = int(prefs.ral_min / 12) if prefs and prefs.ral_min else None
    city, radius = _location_pref(prefs)
    candidate_ctx = _build_candidate_context(cv, prefs)

    logger.info("Iris: ricerca ruoli %s (città=%s, raggio=%s km)", roles, city or "tutta Italia", radius)

    # Due pool: 'near' = entro il raggio dalla città; 'remote' = nazionale (solo
    # remoto, tenuto a prescindere dalla distanza). Senza città → un solo pool.
    near_raw, remote_raw = await _gather_sources(roles, salary_min, city, radius)

    seen: set[str] = set()
    geo_ids: set[str] = set()
    near: list[dict] = []
    for opp in near_raw:
        eid = opp["external_id"]
        if eid and eid not in seen:
            seen.add(eid)
            geo_ids.add(eid)
            near.append(opp)
    remote: list[dict] = []
    for opp in remote_raw:
        eid = opp["external_id"]
        if eid and eid not in seen:
            seen.add(eid)
            remote.append(opp)

    if not near and not remote:
        raise ScoutError("Nessun risultato trovato. Controlla le credenziali API o modifica i ruoli target.")

    near.sort(key=_priority, reverse=True)
    # Nel pool nazionale, dai priorità a chi sembra remoto (così il budget di
    # ranking, limitato, colpisce le offerte davvero remote).
    remote.sort(key=lambda o: (_remote_likely(o), _priority(o)), reverse=True)

    # Budget ranking: 30 totali, ma riserva spazio al remoto quando c'è una città
    to_rank = near[:22] if city else near[:30]
    to_rank += remote[: 30 - len(to_rank)]

    logger.info("Iris: %d vicine + %d nazionali → ranking su %d...", len(near), len(remote), len(to_rank))

    ranked = []
    for opp in to_rank:
        ranked.append(await _rank_opportunity(candidate_ctx, opp))

    # Con città impostata: tieni le offerte nel raggio (qualsiasi modalità) e,
    # dal pool nazionale, SOLO quelle che l'LLM ha classificato come remote.
    if city:
        ranked = [o for o in ranked if o["external_id"] in geo_ids or o.get("work_mode") == "remote"]

    ranked.sort(key=lambda x: x.get("match_score") or 0, reverse=True)
    logger.info("Iris completato: %d offerte rankate (post-filtro)", len(ranked))
    return ranked


async def _gather_sources(
    roles: list[str], salary_min: int | None, city: str | None, radius: int | None
) -> tuple[list[dict], list[dict]]:
    """Ritorna (offerte_vicine, offerte_remote_nazionali). Senza città la prima
    contiene tutto e la seconda è vuota (nessun filtro distanza)."""
    import asyncio

    if not city:
        adzuna, jooble = await asyncio.gather(
            _search_adzuna(roles, salary_min),
            _search_jooble(roles),
        )
        return adzuna + jooble, []

    near_adzuna, near_jooble, far_adzuna, far_jooble = await asyncio.gather(
        _search_adzuna(roles, salary_min, where=city, distance=radius),
        _search_jooble(roles, location=city, radius=radius),
        _search_adzuna(roles, salary_min),          # nazionale → pool remoto
        _search_jooble(roles, location="Italia"),   # nazionale → pool remoto
    )
    return near_adzuna + near_jooble, far_adzuna + far_jooble
