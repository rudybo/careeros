# CareerOS

AI-powered career platform that helps professionals find jobs faster.

## MVP Features

- Upload CV (PDF or DOCX)
- Extract and parse CV with local AI (Ollama)
- Structured career profile
- REST API

## Tech Stack

- **Backend**: Python 3.12 + FastAPI
- **Database**: SQLite (via SQLAlchemy async)
- **AI**: Ollama (local, privacy-first)
- **Frontend**: React + TypeScript *(coming soon)*

## Quick Start

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Start server
uvicorn app.main:app --reload
```

API available at: http://localhost:8000
Docs available at: http://localhost:8000/docs

## Ollama Setup

Install Ollama from https://ollama.com

```bash
ollama pull llama3.2
ollama serve
```

## Run Tests

```bash
cd backend
pytest
```
