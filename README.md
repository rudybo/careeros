# CareerOS

An AI-powered career platform that helps professionals find jobs faster. Built as a portfolio project to demonstrate full-stack development with local LLM integration — from async Python backend to a reactive React frontend.

## What it does

CareerOS runs two AI agents that work together on your real CV and real job postings:

1. **Career Strategist** — analyzes a parsed CV and produces a full career report: target roles with match percentage, skill gaps with acquisition roadmaps, and a prioritized action plan
2. **CV Expert** — takes a parsed CV + a specific job description and optimizes the CV for that exact position: keyword analysis, ATS warnings, section-by-section suggestions, rewritten professional summary, and cover letter hints

All processing runs on a local LLM (Ollama + llama3.2) — no external API keys, no data sent to the cloud.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│          React Frontend  (Vite · port 5173)         │
│  Dashboard · CV · Career Analysis · Applications    │
└────────────────────┬────────────────────────────────┘
                     │  HTTP / proxy
                     ▼
┌─────────────────────────────────────────────────────┐
│           FastAPI Backend  (Uvicorn · port 8000)    │
│   /cv  ·  /cv/{id}/analysis  ·  /applications      │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                   Agents Layer                      │
│   CareerStrategist          CVExpert                │
│   (chain-of-thought)        (keyword matching)      │
│   + post-processing guardrails on both              │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│           Ollama  ·  llama3.2 · 3B · CPU            │
└─────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│        SQLAlchemy async  ·  aiosqlite  ·  SQLite    │
└─────────────────────────────────────────────────────┘
```

**Key design decisions:**

- **Async everywhere** — FastAPI + SQLAlchemy async + BackgroundTasks; long-running LLM calls return `202` immediately, the React frontend polls automatically via TanStack Query
- **Repository pattern** — data access fully isolated from business logic; swapping SQLite → PostgreSQL touches only the engine config
- **Post-processing guardrails** — a deterministic correction layer runs after every LLM response to catch what a 3B model can't reliably avoid: fabricated keyword matches, duplicate roadmap steps, gaps that are already in the CV's skill list
- **Clean layer separation** — models → schemas → repositories → services → agents → endpoints; each layer has a single responsibility
- **JobApplication as central entity** — the `JobApplication` model links a parsed CV to a specific job opening, enabling the full apply → track → optimize loop

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| API | FastAPI 0.115 + Uvicorn |
| ORM | SQLAlchemy 2.0 async |
| Database | SQLite via aiosqlite (PostgreSQL-ready) |
| AI | Ollama 0.6.2 + llama3.2 (3B, local) |
| CV parsing | pdfplumber (PDF) + python-docx (DOCX) |
| Text cleanup | ftfy (unicode normalization) |
| Validation | Pydantic v2 + pydantic-settings |
| Testing | pytest-asyncio + httpx (46 tests, in-memory SQLite) |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS |
| Data fetching | TanStack Query (async polling, caching) |
| Routing | React Router v6 |
| HTTP | Axios |
| Icons | Lucide React |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- [Ollama](https://ollama.com) installed and running
- llama3.2 model: `ollama pull llama3.2`

### Backend

```bash
git clone https://github.com/rudybo/careeros.git

cd careeros/backend
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

pip install -r requirements.txt
cp .env.example .env

uvicorn app.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### Frontend

```bash
cd careeros/frontend
npm install
npm run dev
# → http://localhost:5173
```

The Vite dev server proxies all `/api/*` requests to the backend — no CORS configuration needed.

### Running Tests

```bash
cd backend
pytest tests/ -v
# 46 tests · no Ollama required · in-memory SQLite
```

## UI Walkthrough

| Page | What you can do |
|---|---|
| **Dashboard** | Overview of CVs, applications, and best application status |
| **Curriculum** | Drag-and-drop upload (PDF/DOCX), status polling, list |
| **CV Detail** | View all parsed data, trigger Career Strategist analysis |
| **Career Analysis** | Target roles with match %, skill gaps, prioritized roadmap |
| **Candidature** | Create application by pasting a job description, list all |
| **Application Detail** | Match score bar, keyword diff (green/red), ATS warnings, section suggestions, optimized summary, cover letter hints, lifecycle status buttons |

## Project Structure

```
careeros/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── career_strategist/    # Career analysis agent
│   │   │   │   ├── agent.py          # Chain-of-thought + guardrails
│   │   │   │   └── prompt.md
│   │   │   └── cv_expert/            # CV optimization agent
│   │   │       ├── agent.py          # Keyword matching + guardrails
│   │   │       └── prompt.md
│   │   ├── api/v1/endpoints/
│   │   │   ├── cv.py
│   │   │   ├── analysis.py
│   │   │   └── application.py
│   │   ├── core/
│   │   │   ├── config.py             # pydantic-settings
│   │   │   └── database.py           # Async SQLAlchemy engine
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   ├── repositories/             # Data access layer
│   │   ├── schemas/                  # Pydantic v2 schemas
│   │   └── services/
│   │       ├── cv_extractor.py       # PDF/DOCX text extraction
│   │       └── ollama_service.py     # Ollama client wrapper
│   └── tests/                        # 46 pytest-asyncio tests
└── frontend/
    └── src/
        ├── api/client.ts             # Axios API layer
        ├── components/
        │   ├── Layout.tsx            # Sidebar + routing shell
        │   └── StatusBadge.tsx       # Color-coded status pills
        ├── pages/
        │   ├── Dashboard.tsx
        │   ├── CVPage.tsx            # Upload + list
        │   ├── CVDetail.tsx          # Parsed CV + trigger analysis
        │   ├── AnalysisDetail.tsx    # Career Strategist results
        │   ├── ApplicationsPage.tsx  # List + create form
        │   └── ApplicationDetail.tsx # CV Expert results
        └── types/index.ts            # TypeScript interfaces
```

## API Endpoints

### CV Management

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/cv/upload` | Upload PDF or DOCX |
| `POST` | `/api/v1/cv/{id}/parse` | Start async CV parsing → 202 |
| `GET` | `/api/v1/cv/{id}` | Get CV with parsed data |
| `GET` | `/api/v1/cv/` | List all CVs |

### Career Strategist

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/cv/{id}/analyze` | Start career analysis → 202 |
| `GET` | `/api/v1/cv/{id}/analysis/{analysis_id}` | Get analysis result |
| `GET` | `/api/v1/cv/{id}/analysis` | List all analyses for a CV |

### CV Expert + Job Applications

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/applications/` | Create job application |
| `POST` | `/api/v1/applications/{id}/analyze` | Start CV optimization → 202 |
| `PATCH` | `/api/v1/applications/{id}/status` | Update lifecycle status |
| `GET` | `/api/v1/applications/` | List all applications |
| `GET` | `/api/v1/applications/{id}` | Get application + optimization report |

**Status lifecycle:** `draft` → `analyzing` → `ready` → `applied` → `interview` → `offer` / `rejected`

## Roadmap

- [x] CV upload and async parsing (PDF + DOCX)
- [x] Career Strategist agent (target roles, skill gaps, roadmap)
- [x] CV Expert agent + Job Application tracking
- [x] React frontend (dashboard, CV detail, analysis, applications)
- [ ] Cover letter generation agent
- [ ] Interview preparation agent (Q&A from JD)
- [ ] Application analytics (match score trends)
- [ ] Docker Compose
- [ ] PostgreSQL migration
