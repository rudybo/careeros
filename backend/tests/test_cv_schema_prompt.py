from pathlib import Path

from app.schemas.cv import ParsedCV


def test_old_format_still_validates():
    old = {
        "full_name": "Rudy Botosso",
        "work_experience": [{"company": "Acme", "role": "Dev", "description": "x"}],
    }
    cv = ParsedCV(**old)
    assert cv.linkedin is None
    assert cv.work_experience[0].highlights == []


def test_new_fields_round_trip():
    cv = ParsedCV(
        full_name="Rudy",
        linkedin="https://linkedin.com/in/rudy",
        work_experience=[{"role": "IT Manager", "highlights": ["Supportato oltre 15 aziende"]}],
    )
    again = ParsedCV(**cv.model_dump())
    assert again.linkedin == "https://linkedin.com/in/rudy"
    assert again.work_experience[0].highlights == ["Supportato oltre 15 aziende"]


def test_prompt_mentions_new_fields():
    prompt = (Path(__file__).parent.parent / "app" / "prompts" / "cv_analysis.md").read_text(encoding="utf-8")
    assert "highlights" in prompt
    assert "linkedin" in prompt


def test_projects_default_empty_and_old_json_validates():
    assert ParsedCV(full_name="X").projects == []
    cv = ParsedCV(full_name="X", projects=["81-Flow: piattaforma in Python"])
    assert ParsedCV(**cv.model_dump()).projects == ["81-Flow: piattaforma in Python"]


def test_prompt_mentions_projects():
    prompt = (Path(__file__).parent.parent / "app" / "prompts" / "cv_analysis.md").read_text(encoding="utf-8")
    assert '"projects"' in prompt
    assert "ignore them" not in prompt
