import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.core.json_utils import loads_llm_json
from app.core.llm import LLMError, chat
from app.services.job_fetcher import extract_email, find_emails

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")
_MAX_CHARS = 6000


class JobParserError(Exception):
    pass


class JobMeta(BaseModel):
    company: str | None = None
    role: str | None = None
    advertiser_type: Literal["recruiter", "direct"] | None = None
    contact_email: str | None = None


def _apply_guardrails(result: dict, text: str) -> JobMeta:
    adv = result.get("advertiser_type")
    adv = adv if adv in ("recruiter", "direct") else None

    email = result.get("contact_email")
    if not (isinstance(email, str) and email and email.lower() in {e.lower() for e in find_emails(text)}):
        email = extract_email(text)

    def _s(key: str) -> str | None:
        v = result.get(key)
        return v.strip() if isinstance(v, str) and v.strip() else None

    return JobMeta(company=_s("company"), role=_s("role"), advertiser_type=adv, contact_email=email)


async def parse(text: str) -> JobMeta:
    text = text[:_MAX_CHARS]
    try:
        raw = await chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=300,
        )
    except LLMError as e:
        raise JobParserError(str(e)) from e
    try:
        result = loads_llm_json(raw)
    except ValueError as e:
        logger.error("Job parser: output non JSON: %s", raw[:300])
        raise JobParserError(f"Output non valido dal modello: {e}") from e
    return _apply_guardrails(result, text)
