"""Health-check e riavvio del sistema. Pensato per il pannello "Stato sistema"
nella Dashboard: dice se i task girano e permette un riavvio forzato."""
import logging
import os
import subprocess

from fastapi import APIRouter, Request

from app.core import task_state
from app.core.config import settings
from app.services import telegram_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health")
async def health(request: Request):
    sched = getattr(request.app.state, "scheduler", None)
    jobs = []
    if sched is not None:
        for j in sched.get_jobs():
            jobs.append({
                "id": j.id,
                "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
            })
    scheduler_ok = bool(sched is not None and sched.running and jobs)

    tg = telegram_service.poller_status()
    last_search = task_state.get().get("last_search")

    # Tutto ok se: scheduler attivo con job + poller Telegram vivo (o disattivato di proposito)
    overall_ok = scheduler_ok and (tg["alive"] or not tg["enabled"])

    model = settings.groq_model if settings.llm_provider.lower() == "groq" else settings.ollama_model
    return {
        "ok": overall_ok,
        "llm": {"provider": settings.llm_provider, "model": model},
        "scheduler": {"running": scheduler_ok, "jobs": jobs},
        "telegram": tg,
        "last_search": last_search,
    }


@router.post("/restart")
async def restart():
    """Riavvia backend+frontend in modo distaccato: il nuovo processo sopravvive
    al pkill di quello attuale (lo `sleep 1` lascia tornare questa risposta)."""
    home = os.path.expanduser("~")
    script = os.path.join(home, "run-careeros.sh")
    if not os.path.exists(script):
        return {"status": "error", "message": "run-careeros.sh non trovato (solo su server)."}
    subprocess.Popen(
        f"sleep 1 && bash {script}",
        shell=True,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.warning("Riavvio forzato richiesto dall'interfaccia.")
    return {"status": "restarting", "message": "Riavvio in corso (~10s)."}
