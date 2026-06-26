import json
import logging
from pathlib import Path

from app.core.llm import LLMError, chat

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "cv_analysis.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


class OllamaUnavailableError(Exception):
    pass


class OllamaParsingError(Exception):
    pass


async def parse_cv_with_ollama(raw_text: str) -> dict:
    """Estrae i dati strutturati dal CV via LLM (Groq o Ollama in base a
    LLM_PROVIDER). Il nome storico è mantenuto per compatibilità."""
    try:
        raw_output = await chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"CV to analyze:\n\n{raw_text}"},
            ],
            temperature=0.1,
            max_tokens=4096,
        )
    except LLMError as e:
        raise OllamaUnavailableError(str(e)) from e

    try:
        # Strip markdown code fences if the model wraps the JSON
        if raw_output.startswith("```"):
            raw_output = raw_output.split("```")[1]
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]

        return json.loads(raw_output)
    except json.JSONDecodeError as e:
        logger.error("Risposta LLM non è JSON valido: %s", raw_output[:500])
        raise OllamaParsingError(
            f"Il modello non ha restituito JSON valido: {e}"
        ) from e
