"""Astrazione LLM: una sola funzione chat() che instrada verso Groq (cloud) o
Ollama (locale) in base a settings.llm_provider. Tutti gli agenti la usano,
così cambiare provider è solo una env var (LLM_PROVIDER=groq|ollama)."""
import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLMError(Exception):
    pass


async def chat(
    messages: list[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    """Esegue una chat completion e restituisce il testo della risposta (stripped).

    Instrada verso Groq o Ollama a seconda di settings.llm_provider.
    Solleva LLMError se il provider non è raggiungibile.
    """
    if settings.llm_provider.lower() == "groq":
        return await _chat_groq(messages, temperature, max_tokens)
    return await _chat_ollama(messages, temperature, max_tokens)


async def _chat_groq(messages: list[dict], temperature: float, max_tokens: int) -> str:
    if not settings.groq_api_key:
        raise LLMError("GROQ_API_KEY non configurata nel .env")

    payload = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}

    # Retry su 429 (rate limit) con backoff esponenziale
    delays = [2, 5, 12]
    async with httpx.AsyncClient(timeout=90) as client:
        for attempt, delay in enumerate([0, *delays]):
            if delay:
                await asyncio.sleep(delay)
            try:
                resp = await client.post(_GROQ_URL, json=payload, headers=headers)
            except httpx.HTTPError as e:
                raise LLMError(f"Groq non raggiungibile: {e}") from e

            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                logger.warning(
                    "Groq rate limit (tentativo %d), retry-after=%s", attempt + 1, retry_after
                )
                continue
            if resp.status_code >= 400:
                raise LLMError(f"Groq errore {resp.status_code}: {resp.text[:300]}")

            return resp.json()["choices"][0]["message"]["content"].strip()

    raise LLMError("Groq: rate limit persistente dopo i retry")


async def _chat_ollama(messages: list[dict], temperature: float, max_tokens: int) -> str:
    import ollama

    client = ollama.AsyncClient(host=settings.ollama_base_url)
    try:
        response = await client.chat(
            model=settings.ollama_model,
            messages=messages,
            options={"temperature": temperature, "num_predict": max_tokens},
        )
    except Exception as e:
        raise LLMError(f"Ollama non raggiungibile: {e}") from e
    return response.message.content.strip()
