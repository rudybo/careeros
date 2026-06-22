import json
import logging
from pathlib import Path

import ollama

from app.core.config import settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "cv_analysis.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


class OllamaUnavailableError(Exception):
    pass


class OllamaParsingError(Exception):
    pass


async def parse_cv_with_ollama(raw_text: str) -> dict:
    client = ollama.AsyncClient(host=settings.ollama_base_url)

    try:
        response = await client.chat(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"CV to analyze:\n\n{raw_text}"},
            ],
            options={"temperature": 0.1},
        )
    except Exception as e:
        raise OllamaUnavailableError(
            f"Impossibile raggiungere Ollama su {settings.ollama_base_url}. "
            f"Assicurati che Ollama sia avviato. Errore: {e}"
        ) from e

    raw_output = response.message.content.strip()

    try:
        # Strip markdown code fences if the model wraps the JSON
        if raw_output.startswith("```"):
            raw_output = raw_output.split("```")[1]
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]

        return json.loads(raw_output)
    except json.JSONDecodeError as e:
        logger.error("Risposta Ollama non è JSON valido: %s", raw_output[:500])
        raise OllamaParsingError(
            f"Il modello non ha restituito JSON valido: {e}"
        ) from e
