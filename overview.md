# CareerOS — Overview Tecnico

Piattaforma AI per l'ottimizzazione della carriera: parsing CV, analisi strategica, match offerte di mercato, ottimizzazione candidature, bozze Gmail, notifiche Telegram.

---

## Stack

| Layer | Tecnologie |
|-------|-----------|
| **Frontend** | React 19 + TypeScript + Vite + Tailwind CSS (dark mode `class`) |
| **Backend** | Python 3.12 + FastAPI + Uvicorn + SQLAlchemy async |
| **Database** | SQLite (`backend/careeros.db`) via aiosqlite |
| **LLM (locale)** | Ollama (`llama3.2`) su Docker — usato in dev |
| **LLM (prod)** | Groq (`llama-3.3-70b-versatile`) — usato su srvSviluppo |
| **Scheduler** | APScheduler (cron 08:00 + 19:00 Europe/Rome) |
| **Notifiche** | Bot Telegram `@rudy_jobfinder_bot` |
| **Gmail** | Google OAuth + Gmail API (bozze candidate) |

L'astrazione LLM è in `backend/app/core/llm.py` → `chat()`. Non chiamare mai i client Ollama/Groq direttamente: si sceglie il provider con `LLM_PROVIDER` nel `.env`.

---

## Struttura Directory

```
CareerOS/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/     # Router REST (cv, market, applications, analysis)
│   │   ├── agents/               # 4 agenti AI (career_strategist, cv_expert, cover_letter, market_scout)
│   │   ├── models/               # SQLAlchemy ORM (cv, market, application, analysis)
│   │   ├── repositories/         # Data access layer
│   │   ├── services/             # Business logic (cv_extractor, gmail, telegram)
│   │   ├── schemas/              # Pydantic models I/O
│   │   ├── core/                 # config.py, database.py, llm.py
│   │   ├── prompts/              # Template testo per LLM
│   │   └── main.py               # Entry point FastAPI + scheduler
│   ├── tests/                    # pytest + httpx (46 test)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                # 8 pagine React
│   │   ├── components/           # Layout, StatusBadge, AgentBubble
│   │   ├── api/client.ts         # Axios wrapper
│   │   └── types/index.ts        # TypeScript interfaces
│   └── package.json
├── scripts/
│   ├── deploy.sh                 # Deploy frontend (tar-over-ssh) ± backend
│   └── server-setup.sh
├── start.bat                     # Dev locale: backend :8000 + frontend :5173
├── deploy.bat                    # Deploy verso srvSviluppo
└── CLAUDE.md                     # Linee guida per Claude
```

---

## Endpoint API REST

Base path: `http://localhost:8000/api/v1`

### CV (`/cv`)

| Metodo | Path | Scopo |
|--------|------|-------|
| `POST` | `/cv/upload` | Carica PDF/DOCX → estrae testo → salva con status `uploaded` |
| `POST` | `/cv/{cv_id}/parse` | Parsing LLM in background → 202 Accepted |
| `GET` | `/cv/{cv_id}` | Dettaglio CV con `parsed_data` e status |
| `GET` | `/cv/` | Lista tutti i CV |
| `DELETE` | `/cv/{cv_id}` | Elimina CV + candidature in cascade |

### Analisi Carriera (`/cv` — Minerva)

| Metodo | Path | Scopo |
|--------|------|-------|
| `POST` | `/cv/{cv_id}/analyze` | Avvia analisi carriera → 202 Accepted |
| `GET` | `/cv/{cv_id}/analysis/{analysis_id}` | Risultati: target roles, skill gaps, roadmap |
| `GET` | `/cv/{cv_id}/analysis` | Storico analisi per CV |
| `GET` | `/cv/{cv_id}/roadmap` | Checklist roadmap persistente |
| `PATCH` | `/cv/{cv_id}/roadmap/{itemId}` | Aggiorna status item (`todo`/`done`/`dismissed`) |
| `GET` | `/cv/{cv_id}/ats-keywords` | Checklist keyword ATS (a livello carriera) |
| `PATCH` | `/cv/{cv_id}/ats-keywords/{itemId}` | Aggiorna status keyword (`todo`/`added`/`ignored`/`gap`) |

### Candidature (`/applications` — Vera + Clio)

| Metodo | Path | Scopo |
|--------|------|-------|
| `POST` | `/applications/` | Crea candidatura da company + role + job_description |
| `POST` | `/applications/{id}/analyze` | CV Expert: match_score, keyword diff, ATS warnings → 202 |
| `POST` | `/applications/{id}/cover-letter` | Genera cover letter → 202 Accepted |
| `PATCH` | `/applications/{id}/status` | Lifecycle: `draft`→`applied`→`interview`→`offer`/`rejected` |
| `GET` | `/applications/` | Lista candidature |
| `GET` | `/applications/{id}` | Dettaglio con optimization + cover letter |

### Market (`/market` — Iris)

| Metodo | Path | Scopo |
|--------|------|-------|
| `POST` | `/market/search` | Avvia ricerca (Adzuna + Jooble) → 202 Accepted |
| `GET` | `/market/search/status` | Stato ricerca: running, last_error, last_count |
| `GET` | `/market/opportunities` | Lista offerte con filtro status; default top 10 per match |
| `PATCH` | `/market/opportunities/{id}/status` | Cambia status offerta |
| `POST` | `/market/opportunities/{id}/draft` | Genera bozza Gmail → 202 Accepted |
| `GET` | `/market/preferences` | Preferenze ricerca (RAL, città, ruoli target, settori) |
| `PUT` | `/market/preferences` | Salva/aggiorna preferenze |

### Sistema

| Metodo | Path | Scopo |
|--------|------|-------|
| `GET` | `/api/v1/info` | Provider LLM attivo e modello |
| `GET` | `/health` | Health check |

---

## Modelli Database

### `cvs`
| Campo | Tipo | Note |
|-------|------|------|
| `id` | PK | |
| `filename` | str | |
| `raw_text` | text | Testo estratto dal file |
| `parsed_data` | text (JSON) | Output LLM strutturato |
| `status` | str | `uploaded` → `parsing` → `parsed` \| `error` |
| `created_at`, `updated_at` | datetime UTC | |

### `job_applications`
| Campo | Tipo | Note |
|-------|------|------|
| `id` | PK | |
| `cv_id` | FK → cvs | |
| `company`, `role` | str | |
| `job_description` | text | |
| `status` | str | `draft` / `analyzing` / `ready` / `applied` / `interview` / `offer` / `rejected` / `error` |
| `optimization_data` | text (JSON) | Risultati Vera |
| `cover_letter` | text (JSON) | `{subject, body}` |
| `cover_letter_status` | str | `idle` / `generating` / `ready` / `error` |

### `career_analyses`
| Campo | Tipo | Note |
|-------|------|------|
| `id` | PK | |
| `cv_id` | FK → cvs | |
| `status` | str | `pending` / `analyzing` / `completed` / `error` |
| `analysis_data` | text (JSON) | executive_summary, target_roles[], skill_gaps[], roadmap[] |

### `roadmap_items`
| Campo | Tipo | Note |
|-------|------|------|
| `id` | PK | |
| `cv_id` | FK (indica origine) | Lista unica a livello carriera |
| `action` | text | Descrizione azione |
| `category` | str | `skill`, `cert`, ecc. |
| `impact`, `timeframe` | text, str | Nullable |
| `status` | str | `todo` / `done` / `dismissed` |
| `fingerprint` | str (indexed) | Hash normalizzato per dedup |

### `ats_keyword_items`
| Campo | Tipo | Note |
|-------|------|------|
| `id` | PK | |
| `cv_id` | FK (indica origine) | Lista unica a livello carriera |
| `keyword` | str | |
| `reason` | text | Nullable |
| `status` | str | `todo` / `added` / `ignored` / `gap` |
| `fingerprint` | str (indexed) | Forma canonica (gestisce sinonimi IT/EN) |

### `job_opportunities`
| Campo | Tipo | Note |
|-------|------|------|
| `id` | PK | |
| `external_id` | str (unique) | `adzuna_123`, `jooble_456` |
| `source` | str | `adzuna` / `jooble` |
| `title`, `company`, `location` | str | |
| `url` | text | |
| `salary_min`, `salary_max` | float | Nullable |
| `work_mode` | str | `remote` / `hybrid` / `onsite` |
| `match_score` | int | % calcolato da Iris |
| `status` | str | `new` / `saved` / `dismissed` / `applied` |
| `draft_status` | str | `none` / `generating` / `ready` |
| `draft_id`, `gmail_url` | str, text | ID bozza Gmail + link diretto |
| `notified` | bool | Già inviata su Telegram |

### `user_preferences`
| Campo | Tipo | Note |
|-------|------|------|
| `ral_min`, `ral_max` | int | Stipendio annuo grezzo (€) |
| `city`, `radius_km` | str, int | |
| `work_mode` | str | `remote` / `hybrid` / `onsite` |
| `sectors`, `target_roles` | text (JSON) | Array |
| `contract_type`, `company_size` | str | `startup` / `sme` / `enterprise` |

---

## Agenti AI

### Minerva — Career Strategist (`agents/career_strategist/`)
Input: ParsedCV + roadmap done/dismissed + keyword ATS handled

- Analizza ruoli target con % match
- Identifica skill gap con priorità, timeframe e risorse
- Genera roadmap ordinata per priorità
- Suggerisce keyword ATS
- Guardrails: non ripropone gap già nel CV, deduplica roadmap per fingerprint

### Vera — CV Expert (`agents/cv_expert/`)
Input: ParsedCV + job_description

- `match_score` 0-100
- `matched[]` e `missing[]` keyword
- ATS warnings (formattazione, lunghezza, densità keyword)
- Section suggestions (Summary, Skills, Experience)
- Cover letter hints (tono, angoli, punti chiave)
- Optimized summary riscritta

### Clio — Cover Letter (`agents/cover_letter/`)
Input: ParsedCV + company + role + job_description + ottimizzazione Vera (opz.)

- Genera soggetto email personalizzato
- Genera body cover letter su misura
- Usa i suggerimenti Vera se disponibili

### Iris — Market Scout (`agents/market_scout/`)
Input: ParsedCV + UserPreferences

- Ricerca su Adzuna e Jooble
- Estrae offerte: titolo, company, location, URL, salary, descrizione
- Calcola match_score tramite Vera
- Scheduler APScheduler: cron 08:00 + 19:00 Europe/Rome
- Notifica su Telegram le offerte non notificate con match ≥ soglia (default 70%)

---

## Servizi Backend

| Servizio | Funzioni principali |
|---------|-------------------|
| `cv_extractor.py` | `extract_text(filename, content)` → supporta `.pdf` (pdfplumber) e `.docx` (python-docx); normalizza Unicode con ftfy |
| `gmail_service.py` | `get_gmail_service()` → OAuth token.json; `create_draft(to, subject, body)` → crea bozza Gmail con label "CareerOS", ritorna `{draft_id, gmail_url}` |
| `telegram_service.py` | `send_opportunity(opp)` → 3 bottoni (Genera bozza / Salva / Scarta); `notify_new_opportunities()` → invia offerte non notificate; poller `getUpdates` per callback |

---

## Pagine Frontend

| Pagina | Scopo |
|--------|-------|
| `Dashboard.tsx` | Overview: count CV, distribuzione status candidature, lista agenti |
| `CVPage.tsx` | Upload drag-and-drop, lista CV con status badge, polling su "parsing" |
| `CVDetail.tsx` | Parsed CV (nome, email, skills, esperienze, educazione, certificati), pulsante "Analizza Carriera" |
| `AnalysisDetail.tsx` | Risultati Minerva: target roles, skill gaps, roadmap persistente, keyword ATS |
| `ApplicationsPage.tsx` | Lista candidature con bottoni lifecycle |
| `ApplicationDetail.tsx` | Form job description, match_score bar, keyword diff, ATS warnings, cover letter |
| `MarketPage.tsx` | Preferenze ricerca, lista offerte per match score, filtri status e fonte (Adzuna/Jooble) |
| `Attivita.tsx` | Checklist roadmap + keyword ATS globale (sopravvive ai ricalcoli) |

---

## Variabili d'Ambiente

| Variabile | Default | Scopo |
|-----------|---------|-------|
| `DEBUG` | `false` | Logging level, echo SQL |
| `DATABASE_URL` | `sqlite+aiosqlite:///./careeros.db` | Connessione DB |
| `LLM_PROVIDER` | `ollama` | `ollama` (locale) o `groq` (cloud/prod) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Endpoint Ollama (Docker) |
| `OLLAMA_MODEL` | `llama3.2` | Modello locale |
| `GROQ_API_KEY` | — | API key Groq |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Modello Groq |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | — | API Adzuna (Market Scout) |
| `JOOBLE_API_KEY` | — | API Jooble (Market Scout) |
| `TELEGRAM_BOT_TOKEN` | — | Bot Telegram |
| `TELEGRAM_CHAT_ID` | — | Chat ID destinatario |
| `TELEGRAM_MIN_SCORE` | `70` | Soglia match % per notifiche |

---

## Avvio e Deploy

### Dev locale (Windows)
1. Avvia **Docker Desktop** con container Ollama (ascolta su `localhost:11434`)
2. Esegui `start.bat` dalla root → backend uvicorn `:8000` + frontend Vite `:5173`

Verifica provider: `GET http://localhost:8000/api/v1/info` → `{"provider":"ollama",...}`

### srvSviluppo (192.168.188.123 / 100.86.242.13 via Tailscale)
- App su **porta 5173** (Vite diretto — nginx spento di proposito, VPN Tailscale)
- LLM = Groq (`LLM_PROVIDER=groq` nel `.env`)
- Log backend: `~/backend.log`

### Deploy (NO git, NO npm build)
```bash
# Solo frontend (Vite HMR ricarica da solo):
bash scripts/deploy.sh

# Frontend + backend (riavvia uvicorn):
bash scripts/deploy.sh --backend
```

Scrive il timestamp in `frontend/src/version.ts` (`BUILD_TIME` visibile in UI).

Riavvio backend via SSH:
```bash
ssh SERVER "nohup bash ~/run-careeros.sh >/tmp/x.log 2>&1 &"
```

### Type-check frontend
```bash
cd frontend && npx tsc --noEmit
```

---

## Flusso Operativo Principale

```
1. Upload CV      → POST /cv/upload              → raw_text in DB
2. Parse CV       → POST /cv/{id}/parse          → ParsedCV JSON (LLM)
3. Analisi        → POST /cv/{id}/analyze        → Minerva → roadmap + skill gaps
4. Offerte        → POST /market/search          → Iris → JobOpportunity[] (+ scheduler)
5. Candidatura    → POST /applications/          → job_description
6. Ottimizza CV   → POST /applications/{id}/analyze   → Vera → match_score + warnings
7. Cover letter   → POST /applications/{id}/cover-letter → Clio → Gmail draft
```

Tutte le operazioni lunghe ritornano **202 Accepted**; il frontend fa polling con TanStack Query (`refetchInterval`).

---

## Convenzioni

- **API:** REST/JSON — snake_case Python, camelCase React
- **Env React:** prefisso `VITE_`, accesso `import.meta.env.VITE_VAR`
- **Breakpoint sidebar:** `lg:` (non `md:`)
- **Mobile:** `grid-cols-1`, `pb-24`/`pb-40` dove c'è AgentBubble
- **Git:** commit = milestone stabili (non ogni fix); deploy quotidiano via `deploy.sh`
- **DB async:** SQLAlchemy `AsyncSessionLocal` ovunque
