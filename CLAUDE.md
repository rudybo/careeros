# CLAUDE.md - Web Project Guidelines (Vite + Python)

## Project Architecture & Tech Stack
- **Frontend:** React (gestito tramite Vite), Node.js, Tailwind CSS.
- **Backend:** Python, SQLite (Database).
- **Communication:** REST API / JSON.

## Token & Context Optimization (CRITICAL)
- **Do NOT rewrite whole files:** Mostra solo le righe modificate o la singola funzione aggiornata. Non rigenerare interi componenti React o script Python.
- **Be Concise:** Zero preamboli. Vai dritto al codice o al comando di terminale.
- **No DB Schema Dumps:** Non stampare l'intero schema SQLite se devi modificare una sola query.

## Core Commands & Scripts

### Frontend (React + Vite)
- Directory: `./frontend` (se separata)
- Install: `npm install`
- Dev Server: `npm run dev` (Vite dev server)
- Build/Preview: `npm run build` / `npm run preview`
- Lint: `npm run lint`

### Backend (Python + SQLite)
- Directory: `./backend` (se separata)
- Env Activation: `source .venv/bin/activate` (Mac/Linux) o `.venv\Scripts\activate` (Win)
- Dev Server: [es. `python main.py` o `uvicorn main:app --reload`]
- DB Migration: [es. `python init_db.py`]

## Coding Standards & Constraints
- **Vite/React:** Usa l'importazione dei moduli standard di Vite. Configura le variabili d'ambiente tramite `.env` usando il prefisso `VITE_` (accedi con `import.meta.env.VITE_VAR`).
- **Python:** Usa i type hints. Gestisci sempre le connessioni SQLite usando i contesti `with sqlite3.connect(...) as conn:`.
- **API Responses:** Risposte in formato JSON. Usa lo snake_case lato Python e il camelCase lato React.

## Active Context & Next Steps
- **Current Task:** [Scrivi qui cosa stai facendo ora, es. Configurazione proxy Vite per API Python]
- **Next Step:** [Es. Creazione della prima fetch Axios/Fetch]
