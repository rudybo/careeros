"""I modelli gpt-oss spendono i token di reasoning dentro max_tokens: con lo
sforzo di default ne bruciano ~1000-1900 e troncano il JSON degli agenti.
Il payload deve chiedere reasoning_effort=low su quei modelli, e non inviare
il parametro sui modelli che non lo supportano."""
from unittest.mock import AsyncMock, patch

import pytest

from app.core import llm


def _fake_response():
    resp = AsyncMock()
    resp.status_code = 200
    resp.json = lambda: {"choices": [{"message": {"content": "ok"}}]}
    return resp


async def _capture_payload(model: str) -> dict:
    with patch.object(llm.settings, "groq_model", model), \
         patch.object(llm.settings, "groq_api_key", "test-key"), \
         patch("httpx.AsyncClient.post", new=AsyncMock(return_value=_fake_response())) as post:
        await llm._chat_groq([{"role": "user", "content": "hi"}], 0.1, 2048)
    return post.await_args.kwargs["json"]


@pytest.mark.parametrize("model", ["openai/gpt-oss-120b", "openai/gpt-oss-20b"])
async def test_gpt_oss_chiede_reasoning_basso(model):
    payload = await _capture_payload(model)
    assert payload["reasoning_effort"] == "low"


@pytest.mark.parametrize("model", ["llama-3.3-70b-versatile", "groq/compound", "allam-2-7b"])
async def test_altri_modelli_senza_reasoning_effort(model):
    payload = await _capture_payload(model)
    assert "reasoning_effort" not in payload
