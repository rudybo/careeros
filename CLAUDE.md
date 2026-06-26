# CLAUDE.md — CareerOS

Piattaforma AI per la carriera: parsing CV, analisi strategica (agente Minerva), Market Scout, candidature, bot Telegram.

## Stack
- **Frontend:** React + TypeScript + Vite + Tailwind (dark mode `class`). Dir `frontend/`.
- **Backend:** Python 3.12 (venv via `uv`) + FastAPI + uvicorn + SQLAlchemy async. Dir `backend/`, app `app.main:app`.
- **DB:** SQLite (`backend/careeros.db`).
- **LLM:** astrazione unica `app/core/llm.py` → `chat()`. Provider scelto da `LLM_PROVIDER` nel `.env`: **Groq** (server/prod), **Ollama** (locale/dev). MAI chiamare i client `ollama`/`groq` diretti.
- **API:** REST/JSON. snake_case lato Python, camelCase lato React.

## Token & Context (CRITICO)
- **Non riscrivere interi file:** modifica solo le righe/funzione interessate. Niente rigenerazione di componenti React o script Python interi.
- **Conciso:** zero preamboli, dritto al codice o al comando.
- **Niente dump:** non stampare lo schema DB o file interi per cambiare una query/riga.

## Comandi
### Locale (Windows, dev)
1. **Docker Desktop** (container Ollama) PRIMA — il backend lo contatta su `localhost:11434`.
2. **`start.bat`** (root) → backend uvicorn :8000 + frontend Vite :5173. Libera la porta 8000 da solo.
- Type-check frontend: `cd frontend && npx tsc --noEmit` (Vite dev ignora errori di tipo).
- Verifica backend: `http://localhost:8000/api/v1/info` → `{"provider":"ollama",...}` in locale.

### Server srvSviluppo (192.168.188.123, "prod")
- App SEMPRE su **porta 5173**: `http://192.168.188.123:5173` (LAN) o `http://100.86.242.13:5173` (Tailscale). nginx/:80 **spenti di proposito** (VPN Tailscale, non riproporli).
- LLM = Groq (`/api/v1/info` → `provider:groq`). Ollama NON gira sul server (VM debole).
- Log backend: `~/backend.log`. Niente `sqlite3` CLI → usare `python3 -c "import sqlite3..."`.

## Deploy (NON git)
- `bash scripts/deploy.sh` → copia `frontend/src` via tar-over-ssh; Vite HMR ricarica da solo. Scrive il timestamp in `frontend/src/version.ts` (`BUILD_TIME`, mostrato in UI).
- `bash scripts/deploy.sh --backend` → + `backend/app`, poi riavvia uvicorn via `~/run-careeros.sh`.
- **NIENTE `npm run build`** come step di deploy (serve solo come check tipi). NIENTE nginx.
- Riavvio backend da SSH: `ssh SERVER "nohup bash ~/run-careeros.sh >/tmp/x.log 2>&1 &"` (pkill+restart). `pkill -f uvicorn` diretto chiude la sessione SSH.

## Git (solo versioni stabili)
- Commit = milestone, NON ogni fix. Il deploy quotidiano è separato (`deploy.sh`).
- Dopo commit+push stabile, riallinea il clone server: `ssh SERVER "cd ~/CareerOS && git fetch origin && git reset --hard origin/main"` (sicuro: `careeros.db`/`.env`/segreti non tracciati).
- Chiudi i messaggi di commit con: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## Standard
- **Vite/React:** env con prefisso `VITE_`, accesso `import.meta.env.VITE_VAR`. Breakpoint sidebar `lg:` (non `md:`); `grid-cols-1` su mobile; `pb-24`/`pb-40` dove c'è la barra AgentBubble.
- **Python:** type hints. Sessioni DB async (SQLAlchemy `AsyncSessionLocal`).
