"""Stato persistente dei task automatici (sopravvive ai riavvii del backend).
Salvato come piccolo file JSON accanto al DB. Serve all'indicatore "ultima
ricerca" in pagina e a sapere se i task girano."""
import datetime
import json
from pathlib import Path

_STATE_FILE = Path(__file__).resolve().parent.parent.parent / "task_state.json"


def _read() -> dict:
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(state: dict) -> None:
    try:
        _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def record_search(*, trigger: str, created: int = 0, skipped: int = 0, error: str | None = None) -> None:
    """Registra l'esito dell'ultima ricerca offerte (auto o manuale)."""
    state = _read()
    state["last_search"] = {
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trigger": trigger,
        "created": created,
        "skipped": skipped,
        "error": error,
    }
    _write(state)


def get() -> dict:
    return _read()
