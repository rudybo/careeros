# Bozza candidatura su misura — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Da un link/testo di annuncio creare una bozza Gmail con lettera nel corpo e PDF del CV adattato allegato, registrando se l'annuncio è di recruiter o azienda diretta.

**Architecture:** Pipeline unica `build_tailored_draft()` (servizio, senza DB) chiamata sia dal flusso Candidature sia dal Market Scout. Nuovi pezzi: `job_fetcher` (link → testo), `job_parser` (metadati via LLM), `cv_tailor` (CV adattato + guardia anti-invenzione in codice), `cv_pdf` (ReportLab), `gmail_service` multipart. L'LLM passa SEMPRE da `app.core.llm.chat`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async (SQLite), httpx, ReportLab, Gmail API; React + TS + react-query.

## Global Constraints

- Nessun invio automatico: si crea solo la bozza Gmail (label `CareerOS`), l'utente preme Invia.
- Mai chiamare client `ollama`/`groq` diretti: solo `app.core.llm.chat()`.
- CV adattato: nessuna informazione inventata (aziende, titoli, date, studi, tecnologie solo dal CV base).
- Type hints Python; sessioni DB async (`AsyncSessionLocal`); snake_case Python, camelCase non richiesto (il frontend usa già snake_case dai tipi esistenti).
- Groq free tier: TPM 8000 → input compatti (CV serializzato senza `None`, annuncio troncato a 6000 caratteri).
- Esegui i test dal dir `backend/`: `.venv/Scripts/python -m pytest <path> -v`.
- Commit = milestone (CLAUDE.md): **un solo commit finale** (Task 9), non uno per task. Chiudere con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Niente `npm run build`; type-check frontend con `cd frontend && npx tsc --noEmit`.

## File Structure

| File | Responsabilità |
|---|---|
| `backend/app/models/application.py` (mod) | nuove colonne |
| `backend/app/core/database.py` (mod) | migrazione colonne |
| `backend/app/schemas/application.py` (mod) | create/update/detail con nuovi campi |
| `backend/app/repositories/application_repository.py` (mod) | metodi meta/draft |
| `backend/app/core/json_utils.py` (new) | `loads_llm_json` |
| `backend/app/services/job_fetcher.py` (new) | `fetch_job_posting`, `extract_email`, `JobFetchError` |
| `backend/app/agents/job_parser/{__init__,agent,prompt.md}` (new) | `parse(text) -> JobMeta` |
| `backend/app/agents/cv_tailor/{__init__,agent,prompt.md}` (new) | `tailor(cv, job_text) -> ParsedCV` + guardia |
| `backend/app/services/cv_pdf.py` (new) | `render_cv_pdf(cv) -> bytes` |
| `backend/app/agents/cover_letter/{agent.py,prompt.md}` (mod) | tono per `advertiser_type` |
| `backend/app/services/gmail_service.py` (mod) | multipart + allegati |
| `backend/app/services/application_draft.py` (new) | `build_tailored_draft`, `run_application_draft` |
| `backend/app/api/v1/endpoints/application.py` (mod) | create da link, PATCH, POST draft |
| `backend/app/api/v1/endpoints/market.py` (mod) | `_run_create_draft` delega alla pipeline |
| `backend/tests/*` | test per ogni unità |
| `frontend/src/{types/index.ts,api/client.ts,pages/ApplicationsPage.tsx,pages/ApplicationDetail.tsx}` (mod) | UI |

---

### Task 1: Dati — colonne, schemi, repository

**Files:**
- Modify: `backend/app/models/application.py` (dopo `cover_letter_status`)
- Modify: `backend/app/core/database.py` (in `_migrate_add_columns`)
- Modify: `backend/app/schemas/application.py`
- Modify: `backend/app/repositories/application_repository.py`
- Test: `backend/tests/test_application_draft_data.py`

**Interfaces:**
- Produces (repo): `create(cv_id, company, role, job_description, source_url=None, advertiser_type=None, contact_email=None)`; `set_meta(app_id, advertiser_type: str | None, contact_email: str | None) -> JobApplication | None`; `set_draft_status(app_id, status: str)`; `update_draft(app_id, tailored_cv: dict, cover_letter: dict, draft_url: str)` (setta `draft_status="ready"`, `cover_letter_status="ready"`).
- Produces (schema): `JobApplicationCreate` con `company/role/job_description/source_url` opzionali (validator: serve `job_description` o `source_url`); `JobApplicationUpdate{advertiser_type, contact_email}`; `JobApplicationDetailResponse` con `source_url, advertiser_type, contact_email, tailored_cv: ParsedCV | None, draft_url, draft_status`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_application_draft_data.py
import json

import pytest
from pydantic import ValidationError

from app.models.cv import CV
from app.repositories.application_repository import ApplicationRepository
from app.schemas.application import JobApplicationCreate


async def _cv(db_session) -> int:
    cv = CV(filename="a.pdf", raw_text="x", status="parsed", parsed_data="{}")
    db_session.add(cv)
    await db_session.commit()
    await db_session.refresh(cv)
    return cv.id


def test_create_schema_requires_text_or_url():
    with pytest.raises(ValidationError):
        JobApplicationCreate(cv_id=1)
    JobApplicationCreate(cv_id=1, source_url="https://x.it/job")
    JobApplicationCreate(cv_id=1, company="A", role="B", job_description="testo")


async def test_repo_meta_and_draft(db_session):
    repo = ApplicationRepository(db_session)
    cv_id = await _cv(db_session)
    app = await repo.create(cv_id, "Acme", "Dev", "jd", source_url="https://x.it/j")
    assert app.source_url == "https://x.it/j"
    assert app.draft_status == "idle"

    await repo.set_meta(app.id, "recruiter", "hr@acme.it")
    await repo.set_draft_status(app.id, "generating")
    updated = await repo.update_draft(
        app.id, {"full_name": "R"}, {"subject": "s", "full_text": "t"}, "https://mail.google.com/x"
    )
    assert updated.advertiser_type == "recruiter"
    assert updated.contact_email == "hr@acme.it"
    assert updated.draft_status == "ready"
    assert updated.draft_url == "https://mail.google.com/x"
    assert json.loads(updated.tailored_cv) == {"full_name": "R"}
    assert updated.cover_letter_status == "ready"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_application_draft_data.py -v`
Expected: FAIL (`source_url` / `set_meta` mancanti, schema non permette create senza campi).

- [ ] **Step 3: Implement**

`models/application.py`, dopo la riga `cover_letter_status`:

```python
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    advertiser_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # recruiter / direct
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tailored_cv: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON ParsedCV
    draft_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_status: Mapped[str] = mapped_column(String(50), default="idle")  # idle/generating/ready/error
```

`core/database.py`, in `_migrate_add_columns` dopo la riga `cover_letter_status`:

```python
    await conn.run_sync(_add_if_missing, "job_applications", "source_url", "TEXT")
    await conn.run_sync(_add_if_missing, "job_applications", "advertiser_type", "VARCHAR(20)")
    await conn.run_sync(_add_if_missing, "job_applications", "contact_email", "VARCHAR(255)")
    await conn.run_sync(_add_if_missing, "job_applications", "tailored_cv", "TEXT")
    await conn.run_sync(_add_if_missing, "job_applications", "draft_url", "TEXT")
    await conn.run_sync(_add_if_missing, "job_applications", "draft_status", "VARCHAR(50) DEFAULT 'idle'")
```

`schemas/application.py`: aggiungi `from typing import Literal`, `from pydantic import BaseModel, Field, model_validator`, `from app.schemas.cv import ParsedCV`; sostituisci `JobApplicationCreate` e aggiungi `JobApplicationUpdate`:

```python
AdvertiserType = Literal["recruiter", "direct"]


class JobApplicationCreate(BaseModel):
    cv_id: int
    company: str | None = None
    role: str | None = None
    job_description: str | None = None
    source_url: str | None = None
    advertiser_type: AdvertiserType | None = None
    contact_email: str | None = None

    @model_validator(mode="after")
    def _need_text_or_url(self):
        if not (self.job_description and self.job_description.strip()) and not (
            self.source_url and self.source_url.strip()
        ):
            raise ValueError("Serve il testo dell'annuncio oppure il link.")
        return self


class JobApplicationUpdate(BaseModel):
    advertiser_type: AdvertiserType | None = None
    contact_email: str | None = None
```

In `JobApplicationDetailResponse` aggiungi (dopo `cover_letter_status`):

```python
    source_url: str | None = None
    advertiser_type: AdvertiserType | None = None
    contact_email: str | None = None
    tailored_cv: ParsedCV | None = None
    draft_url: str | None = None
    draft_status: str = "idle"
```

`repositories/application_repository.py`: sostituisci la firma/corpo di `create`:

```python
    async def create(
        self,
        cv_id: int,
        company: str,
        role: str,
        job_description: str,
        source_url: str | None = None,
        advertiser_type: str | None = None,
        contact_email: str | None = None,
    ) -> JobApplication:
        app = JobApplication(
            cv_id=cv_id,
            company=company,
            role=role,
            job_description=job_description,
            source_url=source_url,
            advertiser_type=advertiser_type,
            contact_email=contact_email,
            status="draft",
        )
        self._session.add(app)
        await self._session.commit()
        await self._session.refresh(app)
        return app
```

e aggiungi in fondo alla classe:

```python
    async def set_meta(self, app_id: int, advertiser_type: str | None, contact_email: str | None) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        app.advertiser_type = advertiser_type
        app.contact_email = contact_email
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def set_draft_status(self, app_id: int, status: str) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        app.draft_status = status
        await self._session.commit()
        await self._session.refresh(app)
        return app

    async def update_draft(self, app_id: int, tailored_cv: dict, cover_letter: dict, draft_url: str) -> JobApplication | None:
        app = await self.get_by_id(app_id)
        if app is None:
            return None
        app.tailored_cv = json.dumps(tailored_cv, ensure_ascii=False)
        app.cover_letter = json.dumps(cover_letter, ensure_ascii=False)
        app.cover_letter_status = "ready"
        app.draft_url = draft_url
        app.draft_status = "ready"
        await self._session.commit()
        await self._session.refresh(app)
        return app
```

- [ ] **Step 4: Run test + suite esistente**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_application_draft_data.py tests/test_applications.py tests/test_status_history.py -v`
Expected: PASS. Se `test_applications.py` crea candidature senza `company`/`role`, adegua solo il test (i campi restano accettati).

---

### Task 2: Fetch dell'annuncio da link

**Files:**
- Create: `backend/app/services/job_fetcher.py`
- Modify: `backend/requirements.txt` (httpx diventa dipendenza runtime)
- Test: `backend/tests/test_job_fetcher.py`

**Interfaces:**
- Produces: `class JobFetchError(Exception)`; `extract_email(text: str) -> str | None`; `html_to_text(html: str) -> str`; `async fetch_job_posting(url: str, client: httpx.AsyncClient | None = None) -> str` (solleva `JobFetchError`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_job_fetcher.py
import httpx
import pytest

from app.services.job_fetcher import JobFetchError, extract_email, fetch_job_posting, html_to_text

LONG = "Cerchiamo uno sviluppatore Python con esperienza in FastAPI e SQL. " * 10


def test_html_to_text_strips_scripts_and_tags():
    html = "<html><head><style>x{}</style></head><body><script>var a=1</script><h1>Dev</h1><p>Python  e SQL</p></body></html>"
    text = html_to_text(html)
    assert "var a" not in text and "x{}" not in text
    assert "Dev" in text and "Python e SQL" in text


def test_extract_email():
    assert extract_email("Scrivi a hr@acme.it entro venerdì") == "hr@acme.it"
    assert extract_email("nessuna mail") is None
    assert extract_email("noreply@acme.it oppure jobs@acme.it") == "jobs@acme.it"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


async def test_fetch_ok():
    client = _client(lambda r: httpx.Response(200, text=f"<body><p>{LONG}</p></body>"))
    text = await fetch_job_posting("https://x.it/job", client=client)
    assert "FastAPI" in text


async def test_fetch_login_wall_short_text():
    client = _client(lambda r: httpx.Response(200, text="<body>Accedi per continuare</body>"))
    with pytest.raises(JobFetchError):
        await fetch_job_posting("https://x.it/job", client=client)


async def test_fetch_http_error_and_bad_scheme():
    client = _client(lambda r: httpx.Response(403))
    with pytest.raises(JobFetchError):
        await fetch_job_posting("https://x.it/job", client=client)
    with pytest.raises(JobFetchError):
        await fetch_job_posting("file:///etc/passwd")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_job_fetcher.py -v`
Expected: FAIL (modulo mancante).

- [ ] **Step 3: Implement**

```python
# backend/app/services/job_fetcher.py
"""Scarica una pagina di annuncio e ne estrae il testo leggibile."""
import re
from html.parser import HTMLParser

import httpx

_SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}
_BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_LOGIN_MARKERS = ("accedi", "sign in", "log in", "login", "iscriviti")
_MIN_CHARS = 300
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class JobFetchError(Exception):
    pass


def extract_email(text: str) -> str | None:
    for m in _EMAIL_RE.findall(text):
        if not re.match(r"(no-?reply|donotreply)", m.lower()):
            return m
    return None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    raw = "".join(parser.parts)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in raw.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def _looks_like_login_wall(text: str) -> bool:
    if len(text) < _MIN_CHARS:
        return True
    return len(text) < 1500 and any(m in text.lower() for m in _LOGIN_MARKERS)


async def fetch_job_posting(url: str, client: httpx.AsyncClient | None = None) -> str:
    if not url.lower().startswith(("http://", "https://")):
        raise JobFetchError("Il link deve iniziare con http:// o https://")
    own_client = client is None
    client = client or httpx.AsyncClient(follow_redirects=True, timeout=15, headers={"User-Agent": _UA})
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise JobFetchError(f"Impossibile scaricare la pagina: {e}") from e
    finally:
        if own_client:
            await client.aclose()

    text = html_to_text(resp.text)
    if _looks_like_login_wall(text):
        raise JobFetchError("Pagina non leggibile (login o contenuto vuoto): incolla il testo dell'annuncio.")
    return text
```

`requirements.txt`: sostituisci la riga `httpx>=0.27.0` (sezione Testing) spostandola in una nuova sezione sopra:

```
# HTTP client (job fetcher + test)
httpx>=0.27.0
```
e rimuovila dalla sezione `# Testing`.

- [ ] **Step 4: Run test**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_job_fetcher.py -v`
Expected: PASS (5 test).

---

### Task 3: Parser metadati annuncio (LLM) + utility JSON

**Files:**
- Create: `backend/app/core/json_utils.py`
- Create: `backend/app/agents/job_parser/__init__.py` (vuoto), `agent.py`, `prompt.md`
- Test: `backend/tests/test_job_parser.py`

**Interfaces:**
- Consumes: `app.core.llm.chat`, `LLMError`; `app.services.job_fetcher.extract_email`.
- Produces: `loads_llm_json(raw: str) -> dict`; `class JobMeta(BaseModel){company, role, advertiser_type, contact_email}` (tutti `str | None`); `class JobParserError(Exception)`; `_apply_guardrails(result: dict, text: str) -> JobMeta`; `async parse(text: str) -> JobMeta`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_job_parser.py
from unittest.mock import AsyncMock, patch

from app.agents.job_parser import agent
from app.core.json_utils import loads_llm_json

TEXT = "Selezione per Acme Srl: Backend Developer. Invia il CV a hr@acme.it"


def test_loads_llm_json_strips_fences():
    assert loads_llm_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert loads_llm_json('{"a": 2}') == {"a": 2}


def test_guardrails_invented_email_dropped_real_email_fallback():
    meta = agent._apply_guardrails(
        {"company": "Acme Srl", "role": "Backend Developer", "advertiser_type": "direct", "contact_email": "fake@x.it"},
        TEXT,
    )
    assert meta.contact_email == "hr@acme.it"  # scartata l'inventata, ripiego su regex
    assert meta.advertiser_type == "direct"


def test_guardrails_invalid_advertiser_type():
    meta = agent._apply_guardrails({"advertiser_type": "boh"}, "testo senza email")
    assert meta.advertiser_type is None and meta.contact_email is None


async def test_parse_uses_chat():
    raw = '{"company":"Acme Srl","role":"Backend Developer","advertiser_type":"recruiter","contact_email":null}'
    with patch.object(agent, "chat", new=AsyncMock(return_value=raw)):
        meta = await agent.parse(TEXT)
    assert meta.advertiser_type == "recruiter" and meta.company == "Acme Srl"
    assert meta.contact_email == "hr@acme.it"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_job_parser.py -v`
Expected: FAIL (moduli mancanti).

- [ ] **Step 3: Implement**

```python
# backend/app/core/json_utils.py
import json


def loads_llm_json(raw: str) -> dict:
    """Parsa il JSON di una risposta LLM, tollerando i fence ```json."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
```

```markdown
<!-- backend/app/agents/job_parser/prompt.md -->
You extract structured metadata from an Italian or English job posting.

Return ONLY a valid JSON object, no markdown fences, with exactly these keys:

{
  "company": "hiring company name, or the recruiting agency name if the company is not disclosed, or null",
  "role": "job title as written in the posting, or null",
  "advertiser_type": "recruiter" | "direct" | null,
  "contact_email": "an email address that appears literally in the text, or null"
}

advertiser_type rules:
- "recruiter": posted by a staffing/recruiting/headhunting agency or "per conto di un nostro cliente", "azienda cliente", client not named.
- "direct": posted by the company that will employ the person ("unisciti al nostro team", company talks about itself).
- null if you cannot tell.

Never invent data: if a field is not in the text, use null.
```

```python
# backend/app/agents/job_parser/agent.py
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.core.json_utils import loads_llm_json
from app.core.llm import LLMError, chat
from app.services.job_fetcher import extract_email

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")
_MAX_CHARS = 6000


class JobParserError(Exception):
    pass


class JobMeta(BaseModel):
    company: str | None = None
    role: str | None = None
    advertiser_type: Literal["recruiter", "direct"] | None = None
    contact_email: str | None = None


def _apply_guardrails(result: dict, text: str) -> JobMeta:
    adv = result.get("advertiser_type")
    adv = adv if adv in ("recruiter", "direct") else None

    email = result.get("contact_email")
    if not (isinstance(email, str) and email and email.lower() in text.lower()):
        email = extract_email(text)

    def _s(key: str) -> str | None:
        v = result.get(key)
        return v.strip() if isinstance(v, str) and v.strip() else None

    return JobMeta(company=_s("company"), role=_s("role"), advertiser_type=adv, contact_email=email)


async def parse(text: str) -> JobMeta:
    text = text[:_MAX_CHARS]
    try:
        raw = await chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=300,
        )
    except LLMError as e:
        raise JobParserError(str(e)) from e
    try:
        result = loads_llm_json(raw)
    except ValueError as e:
        logger.error("Job parser: output non JSON: %s", raw[:300])
        raise JobParserError(f"Output non valido dal modello: {e}") from e
    return _apply_guardrails(result, text)
```

- [ ] **Step 4: Run test**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_job_parser.py -v`
Expected: PASS (4 test).

---

### Task 4: CV tailor con guardia anti-invenzione

**Files:**
- Create: `backend/app/agents/cv_tailor/__init__.py` (vuoto), `agent.py`, `prompt.md`
- Test: `backend/tests/test_cv_tailor_guardrails.py`

**Interfaces:**
- Consumes: `loads_llm_json`, `chat`, `LLMError`, `ParsedCV`.
- Produces: `class CVTailorError(Exception)`; `enforce_base_facts(tailored: ParsedCV, base: ParsedCV) -> ParsedCV` (pura, testabile); `async tailor(base: ParsedCV, job_text: str) -> ParsedCV`.

Regole di `enforce_base_facts` (la guardia):
1. `full_name`, `email`, `phone`, `location`, `education`, `languages` sono copiati dal base (mai dall'LLM).
2. Ogni esperienza dell'output deve corrispondere a una del base (stessa `company` normalizzata + stesso `role` normalizzato), senza duplicati; `company/role/start_date/end_date` vengono sovrascritti col base; non corrispondenti → scartate. Nessuna esperienza valida → `CVTailorError`.
3. `skills` e `certifications` filtrate: solo voci presenti nel base (confronto case-insensitive).
4. `description` (e `summary`): se contiene token "tech-like" (maiuscola non iniziale di frase, cifre/`#`/`+`/`.`, sigle) assenti dal testo del CV base → si usa la descrizione/summary del base per quell'elemento.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cv_tailor_guardrails.py
import pytest

from app.agents.cv_tailor.agent import CVTailorError, enforce_base_facts
from app.schemas.cv import Education, ParsedCV, WorkExperience

BASE = ParsedCV(
    full_name="Rudy Botosso", email="r@x.it", phone="1", location="Milano",
    summary="Sviluppatore backend con Python e FastAPI.",
    skills=["Python", "FastAPI", "SQL"],
    work_experience=[
        WorkExperience(company="Acme", role="Backend Developer", start_date="2022", end_date=None,
                       description="Sviluppo API REST con Python e FastAPI su PostgreSQL."),
        WorkExperience(company="Beta", role="Junior Dev", start_date="2019", end_date="2022",
                       description="Manutenzione applicazioni interne."),
    ],
    education=[Education(institution="Uni Milano", degree="Laurea", field="Informatica", year="2019")],
    languages=["Italiano"], certifications=["AWS Cloud Practitioner"],
)


def _tailored(**over) -> ParsedCV:
    data = BASE.model_copy(deep=True)
    for k, v in over.items():
        setattr(data, k, v)
    return data


def test_identity_education_languages_come_from_base():
    out = enforce_base_facts(_tailored(full_name="Mario Rossi", email="evil@x.it", languages=["Klingon"],
                                       education=[Education(institution="MIT")]), BASE)
    assert out.full_name == "Rudy Botosso" and out.email == "r@x.it"
    assert out.languages == ["Italiano"] and out.education[0].institution == "Uni Milano"


def test_invented_company_dropped_and_dates_forced():
    exps = [
        WorkExperience(company="Acme", role="Backend Developer", start_date="1999", end_date="2000",
                       description="Sviluppo API REST con Python."),
        WorkExperience(company="Google", role="CTO", start_date="2020", description="Guida team."),
    ]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert [e.company for e in out.work_experience] == ["Acme"]
    assert out.work_experience[0].start_date == "2022" and out.work_experience[0].end_date is None


def test_no_valid_experience_raises():
    with pytest.raises(CVTailorError):
        enforce_base_facts(_tailored(work_experience=[WorkExperience(company="Google", role="CTO")]), BASE)


def test_invented_skills_and_certs_filtered():
    out = enforce_base_facts(_tailored(skills=["python", "Kubernetes", "SQL"],
                                       certifications=["AWS Cloud Practitioner", "CISSP"]), BASE)
    assert out.skills == ["python", "SQL"]
    assert out.certifications == ["AWS Cloud Practitioner"]


def test_description_with_invented_tech_falls_back_to_base():
    exps = [WorkExperience(company="Acme", role="Backend Developer",
                           description="Sviluppo API con Kubernetes e Terraform in produzione.")]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert out.work_experience[0].description == BASE.work_experience[0].description


def test_keyword_rewrite_without_new_tech_is_kept():
    exps = [WorkExperience(company="Acme", role="Backend Developer",
                           description="Progettazione di API REST scalabili con Python, FastAPI e PostgreSQL.")]
    out = enforce_base_facts(_tailored(work_experience=exps), BASE)
    assert out.work_experience[0].description.startswith("Progettazione di API REST")


def test_summary_with_invented_tech_falls_back():
    out = enforce_base_facts(_tailored(summary="Esperto di Kubernetes e Docker."), BASE)
    assert out.summary == BASE.summary
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cv_tailor_guardrails.py -v`
Expected: FAIL (modulo mancante).

- [ ] **Step 3: Implement**

```markdown
<!-- backend/app/agents/cv_tailor/prompt.md -->
You are an expert CV editor. You receive a candidate's FULL base CV as JSON and a job posting.
Produce a tailored version of the same CV, optimized for that posting, as JSON with the SAME schema:

{"full_name","email","phone","location","summary","skills":[],"work_experience":[{"company","role","start_date","end_date","description"}],"education":[{"institution","degree","field","year"}],"languages":[],"certifications":[]}

What you MAY do:
- Select and reorder work_experience, skills and certifications so the most relevant to the posting come first; omit clearly irrelevant items.
- Rewrite "summary" and each experience "description" using the posting's own keywords and wording, in the language of the base CV.
- Keep descriptions concise (2-4 sentences or short bullet-like sentences).

What you MUST NOT do (hard rules, output is machine-checked and violations are discarded):
- Do NOT invent or alter companies, job titles, dates, degrees, institutions, certifications, languages.
- Do NOT add any technology, tool, skill or achievement that is not already in the base CV, even if the posting asks for it.
- Do NOT change the candidate's name or contact data.

Return ONLY the JSON object, no explanation, no markdown fences.
```

```python
# backend/app/agents/cv_tailor/agent.py
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


def _is_clean(candidate: str | None, base_text: str) -> bool:
    return all(t in base_text for t in _tech_tokens(candidate or ""))


def _find_base_exp(exp: WorkExperience, base: ParsedCV) -> WorkExperience | None:
    for b in base.work_experience:
        if _norm(b.company) == _norm(exp.company) and _norm(b.role) == _norm(exp.role):
            return b
    return None


def enforce_base_facts(tailored: ParsedCV, base: ParsedCV) -> ParsedCV:
    base_text = _cv_text(base)

    exps: list[WorkExperience] = []
    seen: set[tuple[str, str]] = set()
    for exp in tailored.work_experience:
        b = _find_base_exp(exp, base)
        key = (_norm(exp.company), _norm(exp.role))
        if b is None or key in seen:
            logger.warning("CV Tailor: esperienza non verificabile scartata: %s @ %s", exp.role, exp.company)
            continue
        seen.add(key)
        desc = exp.description if _is_clean(exp.description, base_text) else b.description
        if desc != exp.description:
            logger.warning("CV Tailor: descrizione con tecnologie non presenti nel base, uso quella originale (%s)", b.company)
        exps.append(WorkExperience(company=b.company, role=b.role, start_date=b.start_date,
                                   end_date=b.end_date, description=desc))
    if not exps:
        raise CVTailorError("Il CV adattato non contiene esperienze verificabili.")

    base_skills = {_norm(s) for s in base.skills}
    base_certs = {_norm(c) for c in base.certifications}
    summary = tailored.summary if _is_clean(tailored.summary, base_text) else base.summary

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
```

Nota: `_is_clean` confronta token già minuscoli con `base_text` (minuscolo) per sottostringa; "Python", "FastAPI", "PostgreSQL" del base sono ammessi, "Kubernetes"/"Terraform"/"Docker" no. Il caso "REST"/"API" è sigla presente nel base ("API REST") → ok.

- [ ] **Step 4: Run test**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cv_tailor_guardrails.py -v`
Expected: PASS (7 test). Se `test_keyword_rewrite_without_new_tech_is_kept` fallisce perché un token (es. "Progettazione" a inizio frase non conta; "REST", "API", "Python", "FastAPI", "PostgreSQL" sono nel base) controlla quale token manca e correggi il test dati, non la guardia.

---

### Task 5: Rendering PDF del CV

**Files:**
- Modify: `backend/requirements.txt` (aggiungi `reportlab==4.2.5` sotto `# CV parsing`)
- Create: `backend/app/services/cv_pdf.py`
- Test: `backend/tests/test_cv_pdf.py`

**Interfaces:**
- Produces: `render_cv_pdf(cv: ParsedCV) -> bytes` (PDF A4, sezioni: intestazione, sintesi, competenze, esperienze, formazione, lingue, certificazioni; ometti sezioni vuote). Libreria scelta: **ReportLab** (wheel pura Python, nessuna dipendenza di sistema su Windows né sul server; WeasyPrint richiede Pango/GTK).

- [ ] **Step 1: Install**

Run: `cd backend && .venv/Scripts/python -m pip install reportlab==4.2.5`
Expected: `Successfully installed reportlab-4.2.5` (e pillow/chardet se mancanti).

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_cv_pdf.py
import io

import pdfplumber

from app.schemas.cv import Education, ParsedCV, WorkExperience
from app.services.cv_pdf import render_cv_pdf


def test_render_pdf_contains_content():
    cv = ParsedCV(
        full_name="Rudy Botosso", email="r@x.it", phone="123", location="Milano",
        summary="Sviluppatore <backend> & API.",
        skills=["Python", "FastAPI"],
        work_experience=[WorkExperience(company="Acme", role="Backend Developer",
                                        start_date="2022", end_date=None, description="Sviluppo API REST.")],
        education=[Education(institution="Uni Milano", degree="Laurea", field="Informatica", year="2019")],
        languages=["Italiano"], certifications=[],
    )
    pdf = render_cv_pdf(cv)
    assert pdf.startswith(b"%PDF")
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = "\n".join(p.extract_text() or "" for p in doc.pages)
    assert "Rudy Botosso" in text and "Acme" in text and "FastAPI" in text
    assert "<backend> & API" in text  # caratteri speciali escapati correttamente


def test_render_pdf_minimal_cv():
    assert render_cv_pdf(ParsedCV(full_name="Solo Nome")).startswith(b"%PDF")
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cv_pdf.py -v`
Expected: FAIL (modulo mancante).

- [ ] **Step 4: Implement**

```python
# backend/app/services/cv_pdf.py
"""Rendering PDF di un ParsedCV (ReportLab)."""
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from app.schemas.cv import ParsedCV

_ss = getSampleStyleSheet()
_NAME = ParagraphStyle("name", parent=_ss["Title"], fontSize=20, leading=24, alignment=0, spaceAfter=2)
_CONTACT = ParagraphStyle("contact", parent=_ss["Normal"], fontSize=9, textColor=colors.HexColor("#555555"))
_H = ParagraphStyle("h", parent=_ss["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=2,
                    textColor=colors.HexColor("#1f3a5f"))
_BODY = ParagraphStyle("body", parent=_ss["Normal"], fontSize=9.5, leading=13)
_JOB = ParagraphStyle("job", parent=_BODY, fontName="Helvetica-Bold", spaceBefore=4)


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _section(story: list, title: str) -> None:
    story.append(_p(title.upper(), _H))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#c8d0da")))
    story.append(Spacer(1, 3))


def render_cv_pdf(cv: ParsedCV) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=f"CV {cv.full_name}",
                            author=cv.full_name)
    story: list = [_p(cv.full_name, _NAME)]
    contact = " · ".join(x for x in (cv.email, cv.phone, cv.location) if x)
    if contact:
        story.append(_p(contact, _CONTACT))

    if cv.summary:
        _section(story, "Profilo")
        story.append(_p(cv.summary, _BODY))
    if cv.skills:
        _section(story, "Competenze")
        story.append(_p(", ".join(cv.skills), _BODY))
    if cv.work_experience:
        _section(story, "Esperienza professionale")
        for e in cv.work_experience:
            period = f"{e.start_date or ''} – {e.end_date or 'presente'}".strip(" –")
            head = " — ".join(x for x in (e.role, e.company) if x)
            story.append(_p(f"{head}  ({period})" if period else head, _JOB))
            if e.description:
                story.append(_p(e.description, _BODY))
    if cv.education:
        _section(story, "Formazione")
        for ed in cv.education:
            line = ", ".join(x for x in (ed.degree, ed.field, ed.institution, ed.year) if x)
            story.append(_p(line, _BODY))
    if cv.languages:
        _section(story, "Lingue")
        story.append(_p(", ".join(cv.languages), _BODY))
    if cv.certifications:
        _section(story, "Certificazioni")
        story.append(_p(", ".join(cv.certifications), _BODY))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 5: Run test**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cv_pdf.py -v`
Expected: PASS (2 test).

---

### Task 6: Tono della lettera per tipo di inserzionista

**Files:**
- Modify: `backend/app/agents/cover_letter/agent.py` (`_build_context`, `generate`)
- Modify: `backend/app/agents/cover_letter/prompt.md`
- Test: `backend/tests/test_cover_letter_tone.py`

**Interfaces:**
- Produces: `_build_context(cv, company, role, job_description, optimization, advertiser_type: str | None = None)` e `generate(cv, company, role, job_description, optimization, advertiser_type: str | None = None)`. Firme esistenti restano valide.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cover_letter_tone.py
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cover_letter_tone.py -v`
Expected: FAIL (`unexpected keyword advertiser_type`).

- [ ] **Step 3: Implement**

In `agent.py` aggiungi sopra `_build_context`:

```python
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
```

Cambia la firma in `def _build_context(cv, company, role, job_description, optimization, advertiser_type: str | None = None) -> str:` (stessi tipi degli altri parametri) e subito prima di `lines += ["", "JOB DESCRIPTION (excerpt):", ...]` aggiungi:

```python
    if advertiser_type in _TONE:
        lines += ["", _TONE[advertiser_type]]
```

In `generate` cambia la firma in `..., optimization: CVOptimization | None, advertiser_type: str | None = None) -> dict:` e la chiamata in `context = _build_context(cv, company, role, job_description, optimization, advertiser_type)`.

In `prompt.md`, nella lista "The letter must:" aggiungi una riga prima di `- Be in Italian`:

```
- If the input contains an "ADVERTISER:" line, follow its tone and word range instead of the default 110-160 words (never go below 85 words)
```

- [ ] **Step 4: Run test + suite lettera**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cover_letter_tone.py tests/test_cover_letter.py tests/test_cover_letter_guardrails.py -v`
Expected: PASS.

---

### Task 7: Gmail — bozza multipart con allegato

**Files:**
- Modify: `backend/app/services/gmail_service.py`
- Test: `backend/tests/test_gmail_service.py`

**Interfaces:**
- Produces: `_build_message(to: str, subject: str, body: str, attachments: list[tuple[str, bytes]] | None = None) -> email.message.Message`; `create_draft(to, subject, body, attachments: list[tuple[str, bytes]] | None = None) -> dict` (invariato il valore di ritorno `{'draft_id','gmail_url'}`). Allegati = tuple `(filename, bytes)` trattati come PDF.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_gmail_service.py
import base64
import email
from unittest.mock import MagicMock, patch

from app.services import gmail_service


def test_build_message_plain_without_attachments():
    msg = gmail_service._build_message("", "Oggetto", "Corpo")
    assert not msg.is_multipart()
    assert msg["to"] is None
    assert msg["subject"] == "Oggetto"


def test_build_message_with_pdf_attachment():
    msg = gmail_service._build_message("hr@acme.it", "Ogg", "Corpo", [("CV.pdf", b"%PDF-1.4 x")])
    assert msg.is_multipart() and msg["to"] == "hr@acme.it"
    parts = list(msg.walk())
    pdf = next(p for p in parts if p.get_filename() == "CV.pdf")
    assert pdf.get_content_type() == "application/pdf"
    assert pdf.get_payload(decode=True) == b"%PDF-1.4 x"
    body = next(p for p in parts if p.get_content_type() == "text/plain")
    assert body.get_payload(decode=True).decode("utf-8") == "Corpo"


def test_create_draft_sends_raw_with_attachment():
    service = MagicMock()
    service.users().labels().list().execute.return_value = {"labels": [{"name": "CareerOS", "id": "L1"}]}
    service.users().drafts().create().execute.return_value = {"id": "D1", "message": {"id": "M1"}}
    with patch.object(gmail_service, "get_gmail_service", return_value=service):
        res = gmail_service.create_draft("", "Ogg", "Corpo", [("CV.pdf", b"%PDF")])
    assert res["draft_id"] == "D1" and "M1" in res["gmail_url"]
    body = service.users().drafts().create.call_args.kwargs["body"]
    raw = base64.urlsafe_b64decode(body["message"]["raw"])
    parsed = email.message_from_bytes(raw)
    assert any(p.get_filename() == "CV.pdf" for p in parsed.walk())
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_gmail_service.py -v`
Expected: FAIL (`_build_message` mancante).

- [ ] **Step 3: Implement**

In `gmail_service.py` aggiungi import `from email.mime.application import MIMEApplication` e `from email.mime.multipart import MIMEMultipart`, poi sostituisci l'inizio di `create_draft` (le righe da `def create_draft` fino a `raw = ...`) con:

```python
def _build_message(to: str, subject: str, body: str, attachments: list[tuple[str, bytes]] | None = None):
    text = MIMEText(body, "plain", "utf-8")
    if attachments:
        message = MIMEMultipart()
        message.attach(text)
        for filename, data in attachments:
            part = MIMEApplication(data, _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=filename)
            message.attach(part)
    else:
        message = text
    if to:
        message["to"] = to
    message["subject"] = subject
    return message


def create_draft(to: str, subject: str, body: str, attachments: list[tuple[str, bytes]] | None = None) -> dict:
    """Create a Gmail draft in the CareerOS label. Returns {'draft_id', 'gmail_url'}."""
    service = get_gmail_service()
    label_id = _get_or_create_label(service)

    message = _build_message(to, subject, body, attachments)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
```

(il resto della funzione — `draft = service.users().drafts().create(...)` in poi — resta invariato.)

- [ ] **Step 4: Run test**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_gmail_service.py -v`
Expected: PASS (3 test).

---

### Task 8: Pipeline, endpoint e Market Scout

**Files:**
- Create: `backend/app/services/application_draft.py`
- Modify: `backend/app/api/v1/endpoints/application.py`
- Modify: `backend/app/api/v1/endpoints/market.py` (`_run_create_draft`)
- Modify: `backend/tests/conftest.py` (patch del nuovo background task)
- Test: `backend/tests/test_application_draft_pipeline.py`, `backend/tests/test_application_draft_api.py`

**Interfaces:**
- Consumes: `job_fetcher.fetch_job_posting/extract_email/JobFetchError`, `job_parser.parse/JobMeta/JobParserError`, `cv_tailor.tailor/CVTailorError`, `cv_pdf.render_cv_pdf`, `cover_letter_agent.generate(..., advertiser_type)`, `gmail_service.create_draft(..., attachments)`, repo (Task 1).
- Produces:
  - `async build_tailored_draft(cv: ParsedCV, company: str, role: str, job_text: str, advertiser_type: str | None, contact_email: str | None, optimization: CVOptimization | None = None) -> dict` → `{"tailored_cv": dict, "cover_letter": dict, "draft_id": str, "gmail_url": str, "advertiser_type": str | None, "contact_email": str | None}`. Se `advertiser_type` è `None` lo rileva con `job_parser.parse`; se `contact_email` è `None` prova `extract_email(job_text)`.
  - `async run_application_draft(app_id: int) -> None` (background; gestisce `draft_status` e persistenza).
  - Endpoint: `POST /applications/` (accetta link), `PATCH /applications/{id}` (body `JobApplicationUpdate`), `POST /applications/{id}/draft` (202).

- [ ] **Step 1: Write the failing pipeline test**

```python
# backend/tests/test_application_draft_pipeline.py
from unittest.mock import AsyncMock, patch

from app.agents.job_parser.agent import JobMeta
from app.schemas.cv import ParsedCV, WorkExperience
from app.services import application_draft

CV = ParsedCV(full_name="Rudy Botosso",
              work_experience=[WorkExperience(company="Acme", role="Dev", description="x")])


async def test_build_tailored_draft_wires_everything():
    tailored = CV.model_copy(deep=True)
    letter = {"subject": "Candidatura per il ruolo di Dev - Rudy Botosso", "full_text": "testo lettera"}
    with patch.object(application_draft.job_parser, "parse",
                      new=AsyncMock(return_value=JobMeta(advertiser_type="recruiter"))) as parse, \
         patch.object(application_draft.cv_tailor, "tailor", new=AsyncMock(return_value=tailored)), \
         patch.object(application_draft.cover_letter_agent, "generate", new=AsyncMock(return_value=letter)) as gen, \
         patch.object(application_draft, "render_cv_pdf", return_value=b"%PDF-x"), \
         patch.object(application_draft.gmail_service, "create_draft",
                      return_value={"draft_id": "D1", "gmail_url": "https://g/D1"}) as draft:
        res = await application_draft.build_tailored_draft(
            CV, "Acme", "Dev", "annuncio scrivi a hr@acme.it", advertiser_type=None, contact_email=None)

    parse.assert_awaited_once()
    assert gen.await_args.kwargs["advertiser_type"] == "recruiter"
    kwargs = draft.call_args.kwargs
    assert kwargs["to"] == "hr@acme.it" and kwargs["subject"] == letter["subject"]
    assert kwargs["attachments"][0][1] == b"%PDF-x" and kwargs["attachments"][0][0].endswith(".pdf")
    assert res["draft_id"] == "D1" and res["advertiser_type"] == "recruiter"
    assert res["contact_email"] == "hr@acme.it"


async def test_build_tailored_draft_skips_detection_when_known():
    with patch.object(application_draft.job_parser, "parse", new=AsyncMock()) as parse, \
         patch.object(application_draft.cv_tailor, "tailor", new=AsyncMock(return_value=CV)), \
         patch.object(application_draft.cover_letter_agent, "generate",
                      new=AsyncMock(return_value={"subject": "s", "full_text": "t"})), \
         patch.object(application_draft, "render_cv_pdf", return_value=b"%PDF"), \
         patch.object(application_draft.gmail_service, "create_draft",
                      return_value={"draft_id": "D", "gmail_url": "u"}):
        res = await application_draft.build_tailored_draft(
            CV, "Acme", "Dev", "jd", advertiser_type="direct", contact_email="a@b.it")
    parse.assert_not_awaited()
    assert res["advertiser_type"] == "direct" and res["contact_email"] == "a@b.it"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_application_draft_pipeline.py -v`
Expected: FAIL (modulo mancante).

- [ ] **Step 3: Implement the pipeline**

```python
# backend/app/services/application_draft.py
"""Pipeline annuncio → CV adattato + lettera + bozza Gmail con PDF allegato."""
import json
import logging
import re

from app.agents.cover_letter import agent as cover_letter_agent
from app.agents.cv_tailor import agent as cv_tailor
from app.agents.job_parser import agent as job_parser
from app.core.database import AsyncSessionLocal
from app.repositories.application_repository import ApplicationRepository
from app.repositories.cv_repository import CVRepository
from app.schemas.application import CVOptimization
from app.schemas.cv import ParsedCV
from app.services import gmail_service
from app.services.cv_pdf import render_cv_pdf
from app.services.job_fetcher import extract_email

logger = logging.getLogger(__name__)


def _pdf_filename(full_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", full_name).strip("_") or "CV"
    return f"CV_{safe}.pdf"


async def build_tailored_draft(
    cv: ParsedCV,
    company: str,
    role: str,
    job_text: str,
    advertiser_type: str | None,
    contact_email: str | None,
    optimization: CVOptimization | None = None,
) -> dict:
    if advertiser_type is None:
        try:
            advertiser_type = (await job_parser.parse(job_text)).advertiser_type
        except job_parser.JobParserError as e:
            logger.warning("Rilevamento tipo inserzionista fallito, procedo senza: %s", e)
    contact_email = contact_email or extract_email(job_text)

    tailored = await cv_tailor.tailor(cv, job_text)
    letter = await cover_letter_agent.generate(
        cv=tailored, company=company, role=role, job_description=job_text,
        optimization=optimization, advertiser_type=advertiser_type,
    )
    pdf = render_cv_pdf(tailored)
    draft = gmail_service.create_draft(
        to=contact_email or "",
        subject=letter["subject"],
        body=letter["full_text"],
        attachments=[(_pdf_filename(cv.full_name), pdf)],
    )
    return {
        "tailored_cv": tailored.model_dump(),
        "cover_letter": letter,
        "draft_id": draft["draft_id"],
        "gmail_url": draft["gmail_url"],
        "advertiser_type": advertiser_type,
        "contact_email": contact_email,
    }


async def run_application_draft(app_id: int) -> None:
    """Background task del flusso Candidature: salva stato e risultati sul record."""
    async with AsyncSessionLocal() as session:
        repo = ApplicationRepository(session)
        try:
            record = await repo.get_by_id(app_id)
            cv_row = await CVRepository(session).get_by_id(record.cv_id)
            optimization = CVOptimization(**json.loads(record.optimization_data)) if record.optimization_data else None
            res = await build_tailored_draft(
                ParsedCV(**json.loads(cv_row.parsed_data)), record.company, record.role,
                record.job_description, record.advertiser_type, record.contact_email, optimization,
            )
            await repo.set_meta(app_id, res["advertiser_type"], res["contact_email"])
            await repo.update_draft(app_id, res["tailored_cv"], res["cover_letter"], res["gmail_url"])
            logger.info("Bozza su misura creata: application_id=%d draft_id=%s", app_id, res["draft_id"])
        except Exception as e:  # CVTailorError, CoverLetterError, RuntimeError (Gmail), ...
            logger.error("Bozza su misura fallita: application_id=%d error=%s", app_id, e, exc_info=True)
            await repo.set_draft_status(app_id, "error")
```

- [ ] **Step 4: Run pipeline test**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_application_draft_pipeline.py -v`
Expected: PASS (2 test).

- [ ] **Step 5: Write the failing API test**

```python
# backend/tests/test_application_draft_api.py
from unittest.mock import AsyncMock, patch

from app.agents.job_parser.agent import JobMeta
from app.services.job_fetcher import JobFetchError
from tests.test_applications import _create_parsed_cv


async def test_create_from_url_fills_meta(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    meta = JobMeta(company="Acme", role="Dev", advertiser_type="recruiter", contact_email="hr@acme.it")
    with patch("app.api.v1.endpoints.application.fetch_job_posting", new=AsyncMock(return_value="testo annuncio")), \
         patch("app.api.v1.endpoints.application.job_parser.parse", new=AsyncMock(return_value=meta)):
        r = await client.post("/api/v1/applications/", json={"cv_id": cv_id, "source_url": "https://x.it/j"})
    assert r.status_code == 201, r.text
    detail = await client.get(f"/api/v1/applications/{r.json()['id']}")
    d = detail.json()
    assert d["company"] == "Acme" and d["advertiser_type"] == "recruiter"
    assert d["contact_email"] == "hr@acme.it" and d["source_url"] == "https://x.it/j"
    assert d["job_description"] == "testo annuncio"


async def test_create_from_url_fetch_failure_is_422(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    with patch("app.api.v1.endpoints.application.fetch_job_posting",
               new=AsyncMock(side_effect=JobFetchError("incolla il testo"))):
        r = await client.post("/api/v1/applications/", json={"cv_id": cv_id, "source_url": "https://x.it/j"})
    assert r.status_code == 422
    assert "incolla" in r.json()["detail"]


async def test_create_without_text_or_url_is_422(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    r = await client.post("/api/v1/applications/", json={"cv_id": cv_id})
    assert r.status_code == 422


async def test_patch_meta_and_start_draft(client, db_session):
    cv_id = await _create_parsed_cv(db_session)
    r = await client.post("/api/v1/applications/", json={
        "cv_id": cv_id, "company": "Acme", "role": "Dev", "job_description": "jd"})
    app_id = r.json()["id"]

    p = await client.patch(f"/api/v1/applications/{app_id}", json={"advertiser_type": "direct", "contact_email": "a@b.it"})
    assert p.status_code == 200
    d = (await client.get(f"/api/v1/applications/{app_id}")).json()
    assert d["advertiser_type"] == "direct" and d["contact_email"] == "a@b.it"

    started = await client.post(f"/api/v1/applications/{app_id}/draft")
    assert started.status_code == 202
    d = (await client.get(f"/api/v1/applications/{app_id}")).json()
    assert d["draft_status"] == "generating"
    again = await client.post(f"/api/v1/applications/{app_id}/draft")
    assert again.status_code == 409
```

(Se `tests` non è importabile come package: `tests/__init__.py` esiste già, quindi `from tests.test_applications import ...` funziona lanciando pytest da `backend/`.)

- [ ] **Step 6: Run to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_application_draft_api.py -v`
Expected: FAIL.

- [ ] **Step 7: Implement endpoints**

`tests/conftest.py`: nel blocco `with patch(...)` aggiungi `\` e una riga:

```python
         patch("app.api.v1.endpoints.application.run_application_draft", new_callable=AsyncMock):
```
(spostando i `:` finali di conseguenza: l'ultimo patch esistente `_run_cover_letter` perde il `:` e termina con ` \`).

`endpoints/application.py`: aggiungi agli import

```python
from app.agents.job_parser import agent as job_parser
from app.schemas.application import JobApplicationUpdate
from app.services.application_draft import run_application_draft
from app.services.job_fetcher import JobFetchError, fetch_job_posting
```

Sostituisci il corpo di `create_application` da `repo = ApplicationRepository(db)` fino al `return record` con:

```python
    job_text = (body.job_description or "").strip()
    company, role = body.company, body.role
    advertiser_type, contact_email = body.advertiser_type, body.contact_email

    if not job_text:
        try:
            job_text = await fetch_job_posting(body.source_url)
        except JobFetchError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    if body.source_url or not (company and role):
        try:
            meta = await job_parser.parse(job_text)
        except job_parser.JobParserError as e:
            logger.warning("Job parser fallito: %s", e)
            meta = job_parser.JobMeta()
        company = company or meta.company
        role = role or meta.role
        advertiser_type = advertiser_type or meta.advertiser_type
        contact_email = contact_email or meta.contact_email

    if not (company and role):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Non riesco a ricavare azienda e ruolo dall'annuncio: compilali a mano.",
        )

    repo = ApplicationRepository(db)
    record = await repo.create(
        cv_id=body.cv_id,
        company=company,
        role=role,
        job_description=job_text,
        source_url=body.source_url,
        advertiser_type=advertiser_type,
        contact_email=contact_email,
    )
    logger.info("Candidatura creata: id=%d company=%s role=%s", record.id, record.company, record.role)
    return record
```

In `_build_detail` aggiungi ai kwargs di `JobApplicationDetailResponse(...)`:

```python
        source_url=record.source_url,
        advertiser_type=record.advertiser_type,
        contact_email=record.contact_email,
        tailored_cv=ParsedCV(**json.loads(record.tailored_cv)) if record.tailored_cv else None,
        draft_url=record.draft_url,
        draft_status=record.draft_status or "idle",
```

Aggiungi, prima di `@router.patch("/{app_id}/status"...)`:

```python
@router.patch("/{app_id}", response_model=JobApplicationResponse)
async def update_meta(app_id: int, body: JobApplicationUpdate, db: AsyncSession = Depends(get_db)):
    repo = ApplicationRepository(db)
    record = await repo.set_meta(app_id, body.advertiser_type, body.contact_email)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    return record


@router.post("/{app_id}/draft", status_code=status.HTTP_202_ACCEPTED)
async def create_tailored_draft(
    app_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    repo = ApplicationRepository(db)
    record = await repo.get_by_id(app_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidatura non trovata.")
    if record.draft_status == "generating":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bozza già in generazione.")
    cv = await CVRepository(db).get_by_id(record.cv_id)
    if cv is None or not cv.parsed_data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV non parsato.")

    await repo.set_draft_status(app_id, "generating")
    background_tasks.add_task(run_application_draft, app_id)
    return {"application_id": app_id, "draft_status": "generating"}
```

`endpoints/market.py`: sostituisci il corpo del `try` interno di `_run_create_draft` (da `cv = ParsedCV(...)` a `await repo.update_draft(...)`) con:

```python
                cv = ParsedCV(**cv_parsed_data)
                result = await build_tailored_draft(
                    cv, company, title, description,
                    advertiser_type=None, contact_email=None,
                )
                await repo.update_draft(opp_id, result["draft_id"], result["gmail_url"])
                logger.info("Bozza Gmail creata per opportunità %d: %s", opp_id, result["draft_id"])
```
e allarga l'`except (CoverLetterError, RuntimeError)` a `except (CoverLetterError, CVTailorError, RuntimeError)`; aggiungi gli import `from app.services.application_draft import build_tailored_draft` e `from app.agents.cv_tailor.agent import CVTailorError`. Lascia gli import `cover_letter_agent`/`gmail_service` se usati altrove nel file (verifica con grep, rimuovi solo se orfani).

- [ ] **Step 8: Run backend suite**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: tutti PASS (inclusi i test esistenti).

---

### Task 9: Frontend, verifica e commit

**Files:**
- Modify: `frontend/src/types/index.ts` (`JobApplicationDetail`)
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/ApplicationsPage.tsx`
- Modify: `frontend/src/pages/ApplicationDetail.tsx`

**Interfaces:**
- Consumes (API): `POST /applications/` con `source_url`; `PATCH /applications/{id}`; `POST /applications/{id}/draft`; dettaglio con `advertiser_type, contact_email, source_url, draft_url, draft_status`.

- [ ] **Step 1: Tipi** — in `types/index.ts` aggiungi a `JobApplicationDetail`:

```ts
  source_url: string | null
  advertiser_type: 'recruiter' | 'direct' | null
  contact_email: string | null
  draft_url: string | null
  draft_status: 'idle' | 'generating' | 'ready' | 'error'
```

- [ ] **Step 2: Client** — in `api/client.ts` sostituisci `createApplication` e aggiungi due funzioni:

```ts
export const createApplication = (data: {
  cv_id: number
  company?: string
  role?: string
  job_description?: string
  source_url?: string
}) => api.post<JobApplication>('/applications/', data).then(r => r.data)

export const updateApplicationMeta = (
  appId: number,
  data: { advertiser_type: 'recruiter' | 'direct' | null; contact_email: string | null },
) => api.patch<JobApplication>(`/applications/${appId}`, data).then(r => r.data)

export const startTailoredDraft = (appId: number) =>
  api.post(`/applications/${appId}/draft`)
```

- [ ] **Step 3: Form Candidature** (`ApplicationsPage.tsx`)
  - Stato: `form` diventa `{ cv_id: '', source_url: '', company: '', role: '', job_description: '' }` (anche nel reset in `onSuccess`).
  - Validazione in `mutationFn`: sostituisci il controllo con
    ```ts
    const hasText = form.company && form.role && form.job_description
    if (!form.cv_id || (!form.source_url && !hasText)) {
      throw new Error('Inserisci il link dell’annuncio oppure compila azienda, ruolo e testo')
    }
    ```
  - `createApplication({ cv_id: Number(form.cv_id), source_url: form.source_url || undefined, company: form.company || undefined, role: form.role || undefined, job_description: form.job_description || undefined })`.
  - Aggiungi, dopo il select del CV, un campo input "Link annuncio (opzionale)" con stesse classi dei campi esistenti, `value={form.source_url}`, placeholder `https://...`, e sotto un testo `text-xs text-gray-400`: "Se il link non è leggibile (es. LinkedIn), incolla il testo qui sotto."
  - Le label di Azienda/Ruolo/Testo diventano "(opzionale con link)" se `form.source_url` è valorizzato (solo testo della label).
  - `onError`: ordine invariato (`e?.message ?? e?.response?.data?.detail`) → inverti in `e?.response?.data?.detail ?? e?.message ?? 'Errore'` così il 422 del backend (fetch fallito) è mostrato.

- [ ] **Step 4: Dettaglio** (`ApplicationDetail.tsx`)
  - Import: `startTailoredDraft, updateApplicationMeta` da `../api/client`; icona `MailIcon, ExternalLinkIcon` da `lucide-react` (aggiungi all'import esistente).
  - `refetchInterval`: aggiungi `if (d.draft_status === 'generating') return 2000`.
  - Mutations:
    ```tsx
    const createDraft = useMutation({
      mutationFn: () => startTailoredDraft(appId),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['application', appId] }),
    })
    const saveMeta = useMutation({
      mutationFn: (v: { advertiser_type: 'recruiter' | 'direct' | null; contact_email: string | null }) =>
        updateApplicationMeta(appId, v),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['application', appId] }),
    })
    ```
  - Card "Bozza Gmail" da inserire subito PRIMA del blocco `{/* ── Cover Letter Generator ── */}` (stesse classi `bg-white rounded-xl border border-gray-200 p-5`):
    - Titolo `MailIcon` + "Bozza email (CV su misura + lettera)".
    - Riga selettore tipo: `<select>` con opzioni `''` ("Non rilevato"), `recruiter` ("Recruiter"), `direct` ("Azienda diretta"), `value={app.advertiser_type ?? ''}`, `onChange` → `saveMeta.mutate({ advertiser_type: (e.target.value || null) as any, contact_email: app.contact_email })`.
    - Input email destinatario con `defaultValue={app.contact_email ?? ''}`, `onBlur` → `saveMeta.mutate({ advertiser_type: app.advertiser_type, contact_email: e.target.value.trim() || null })`.
    - Se `app.source_url`: link `<a href={app.source_url} target="_blank" rel="noreferrer">` "Annuncio originale".
    - Stati di `app.draft_status`: `idle` → bottone "Crea bozza Gmail"; `generating` → riquadro con `Loader2Icon` animato "Sto adattando il CV e preparando la bozza..."; `ready` → riquadro verde con link `app.draft_url` "Apri bozza in Gmail" (`ExternalLinkIcon`) + testo "Controlla e premi Invia" + piccolo bottone "Rigenera"; `error` → riquadro rosso "Creazione bozza fallita (controlla Gmail/log)" + bottone "Riprova".
    - Il bottone è `disabled={createDraft.isPending}`; stili come i bottoni viola esistenti ma `bg-blue-600 hover:bg-blue-700`.

- [ ] **Step 5: Type-check frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: nessun errore.

- [ ] **Step 6: Verifica end-to-end manuale** (Docker/Ollama non necessario se `LLM_PROVIDER=groq` nel `.env` locale; Gmail già autenticato via `token.json`)

1. `start.bat`, apri `http://localhost:5173/applications`.
2. Nuova candidatura con un link pubblico di annuncio → si apre il dettaglio con azienda/ruolo/tipo precompilati.
3. "Crea bozza Gmail" → in Gmail, label CareerOS: bozza con lettera nel corpo e `CV_<nome>.pdf` allegato; destinatario compilato solo se l'annuncio contiene un'email.
4. Apri il PDF: verifica che esperienze/competenze siano tutte presenti nel CV base (nessuna invenzione).
5. Prova un link non leggibile (es. LinkedIn): l'UI mostra il messaggio "incolla il testo".

- [ ] **Step 7: Commit (milestone)**

```bash
git add backend frontend docs
git commit -m "feat: bozza Gmail su misura (CV adattato PDF + lettera) da link annuncio

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Poi (se l'utente vuole il server allineato): `bash scripts/deploy.sh --backend`. **Nota deploy:** sul server serve `pip install reportlab==4.2.5` nel venv prima del riavvio e `credentials.json`/`token.json` Gmail presenti (non tracciati).
