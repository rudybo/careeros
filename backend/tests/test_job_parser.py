from unittest.mock import AsyncMock, patch

from app.agents.job_parser import agent
from app.core.json_utils import loads_llm_json

TEXT = "Selezione per Acme Srl: Backend Developer. Invia il CV a hr@acme.it"


def test_loads_llm_json_strips_fences():
    assert loads_llm_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert loads_llm_json('{"a": 2}') == {"a": 2}


def test_guardrails_invented_email_dropped_real_email_fallback():
    meta = agent._apply_guardrails(
        {"company": "Acme Srl", "role": "Backend Developer", "advertiser_type": "direct", "contact_email": "fake@x.it"},
        TEXT,
    )
    assert meta.contact_email == "hr@acme.it"  # scartata l'inventata, ripiego su regex
    assert meta.advertiser_type == "direct"


def test_guardrails_invalid_advertiser_type():
    meta = agent._apply_guardrails({"advertiser_type": "boh"}, "testo senza email")
    assert meta.advertiser_type is None and meta.contact_email is None


async def test_parse_uses_chat():
    raw = '{"company":"Acme Srl","role":"Backend Developer","advertiser_type":"recruiter","contact_email":null}'
    with patch.object(agent, "chat", new=AsyncMock(return_value=raw)):
        meta = await agent.parse(TEXT)
    assert meta.advertiser_type == "recruiter" and meta.company == "Acme Srl"
    assert meta.contact_email == "hr@acme.it"


import pytest


@pytest.mark.parametrize("raw", ["[1, 2]", '"x"', "null"])
def test_loads_llm_json_rejects_non_dict(raw):
    with pytest.raises(ValueError):
        loads_llm_json(raw)


async def test_parse_non_dict_json_raises_parser_error():
    with patch.object(agent, "chat", new=AsyncMock(return_value="[1,2]")):
        with pytest.raises(agent.JobParserError):
            await agent.parse(TEXT)


def test_guardrails_truncated_email_not_accepted():
    meta = agent._apply_guardrails({"contact_email": "b@acme.it"}, "Scrivi a ab@acme.it")
    assert meta.contact_email == "ab@acme.it"


def test_guardrails_mixed_case_email_accepted():
    meta = agent._apply_guardrails({"contact_email": "hr@acme.it"}, "Scrivi a no-reply@acme.it o HR@Acme.it")
    assert meta.contact_email == "hr@acme.it"
