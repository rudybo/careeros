import json


def loads_llm_json(raw: str) -> dict:
    """Parsa il JSON di una risposta LLM, tollerando i fence ```json."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Il JSON non è un oggetto")
    return data
