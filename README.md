# CareerOS

An AI-powered career platform that helps professionals find jobs faster. Built as a portfolio project to demonstrate production-grade Python backend development with local LLM integration.

## What it does

CareerOS runs two AI agents that work together:

1. **Career Strategist** — analyzes a parsed CV and produces a full career report: target roles with match percentage, skill gaps with acquisition roadmaps, and a prioritized action plan
2. **CV Expert** — takes a parsed CV + a specific job description and optimizes the CV for that exact position: keyword analysis, ATS warnings, section-by-section suggestions, and a rewritten professional summary

Both agents run on a local LLM (Ollama + llama3.2) — no external API keys required.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                        FastAPI                           │
│   /cv  │  /cv/{id}/analysis  │  /applications           │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│                   Agents Layer                  │
│  CareerStrategist        CVExpert               │
│  (chain-of-thought)      (keyword matching)     │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│              Ollama (local LLM)                 │
│              llama3.2 · 3B params · CPU         │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│           Repositories / SQLAlchemy             │
│           async · aiosqlite · SQLite            │
└─────────────────────────────────────────────────┘
```

**Key design decisions:**

- **Async everywhere** — FastAPI + SQLAlchemy async + BackgroundTasks; long-running LLM calls return 202 immediately, client polls for results
- **Repository pattern** — data access is fully isolated from business logic; swapping SQLite for PostgreSQL requires touching only the engine config
- **Post-processing guardrails** — a deterministic correction layer runs after every LLM response to catch hallucinations the 3B model can't reliably avoid (fabricated keyword matches, duplicate roadmap steps, skills already present in the CV flagged as gaps)
- **Clean layer separation** — models → schemas → repositories → services → agents → endpoints; each layer has a single responsibility

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.115 + Uvicorn |
| ORM | SQLAlchemy 2.0 async |
| Database | SQLite via aiosqlite (PostgreSQL-ready) |
| AI | Ollama 0.4.4 + llama3.2 (3B, local) |
| CV parsing | pdfplumber (PDF) + python-docx (DOCX) |
| Text cleanup | ftfy (unicode normalization) |
| Validation | Pydantic v2 + pydantic-settings |
| Testing | pytest-asyncio + httpx (in-memory SQLite) |

## API Endpoints

### CV Management

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/cv/upload` | Upload a PDF or DOCX file |
| `POST` | `/api/v1/cv/{id}/parse` | Start async CV parsing with Ollama → 202 |
| `GET` | `/api/v1/cv/{id}` | Get CV with parsed data |
| `GET` | `/api/v1/cv/` | List all CVs |

### Career Strategist Agent

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/cv/{id}/analyze` | Start career analysis → 202 |
| `GET` | `/api/v1/cv/{id}/analysis/{analysis_id}` | Get analysis result |
| `GET` | `/api/v1/cv/{id}/analysis` | List all analyses for a CV |

### CV Expert + Job Applications

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/applications/` | Create a job application (links CV + JD) |
| `POST` | `/api/v1/applications/{id}/analyze` | Start CV optimization → 202 |
| `PATCH` | `/api/v1/applications/{id}/status` | Update lifecycle status |
| `GET` | `/api/v1/applications/` | List all applications |
| `GET` | `/api/v1/applications/{id}` | Get application with full optimization report |

**Application status lifecycle:** `draft` → `analyzing` → `ready` → `applied` → `interview` → `offer` / `rejected`

## Getting Started

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com) installed and running
- llama3.2 model pulled: `ollama pull llama3.2`

### Setup

```bash
git clone https://github.com/rudybo/careeros.git
cd careeros/backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Start the server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs (Swagger UI): `http://localhost:8000/docs`

### Running Tests

```bash
cd backend
pytest tests/ -v
```

Tests run against an in-memory SQLite database with background tasks stubbed — no Ollama connection required. 46 tests covering API integration, agent guardrails, and CV extraction.

## Project Structure

```
backend/
├── app/
│   ├── agents/
│   │   ├── career_strategist/    # Career analysis agent
│   │   │   ├── agent.py          # Chain-of-thought analysis + guardrails
│   │   │   └── prompt.md         # System prompt
│   │   └── cv_expert/            # CV optimization agent
│   │       ├── agent.py          # Keyword matching + guardrails
│   │       └── prompt.md         # System prompt
│   ├── api/v1/endpoints/
│   │   ├── cv.py                 # CV upload and parsing
│   │   ├── analysis.py           # Career Strategist endpoints
│   │   └── application.py        # CV Expert + job tracking
│   ├── core/
│   │   ├── config.py             # pydantic-settings configuration
│   │   └── database.py           # Async SQLAlchemy engine
│   ├── models/                   # SQLAlchemy ORM models
│   ├── repositories/             # Data access layer
│   ├── schemas/                  # Pydantic v2 schemas
│   └── services/
│       ├── cv_extractor.py       # PDF/DOCX text extraction
│       └── ollama_service.py     # Ollama client wrapper
└── tests/                        # 46 pytest-asyncio tests
```

## Example Workflow

```bash
# 1. Upload your CV
curl -X POST http://localhost:8000/api/v1/cv/upload \
  -F "file=@my_cv.pdf"
# → {"id": 1, "status": "pending"}

# 2. Parse the CV with Ollama
curl -X POST http://localhost:8000/api/v1/cv/1/parse
# → 202 {"status": "parsing"}

# 3. Poll until parsed
curl http://localhost:8000/api/v1/cv/1
# → {"status": "parsed", "parsed_data": {...}}

# 4. Get career strategy
curl -X POST http://localhost:8000/api/v1/cv/1/analyze
# → 202, poll GET /api/v1/cv/1/analysis/1 until status=completed

# 5. Optimize CV for a specific job
curl -X POST http://localhost:8000/api/v1/applications/ \
  -H "Content-Type: application/json" \
  -d '{"cv_id": 1, "company": "Stripe", "role": "Backend Engineer", "job_description": "..."}'
# → {"id": 1, "status": "draft"}

curl -X POST http://localhost:8000/api/v1/applications/1/analyze
# → 202, poll GET /api/v1/applications/1 until status=ready
# → optimization.match_score, missing_keywords, section_suggestions, ...
```

## Roadmap

- [ ] React frontend dashboard
- [ ] Cover letter generation agent
- [ ] Interview preparation agent (Q&A from JD)
- [ ] Application analytics (match score trends over time)
- [ ] Docker Compose setup
- [ ] PostgreSQL migration
