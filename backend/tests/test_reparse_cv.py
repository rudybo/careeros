import json
from unittest.mock import AsyncMock, patch

from app.repositories.cv_repository import CVRepository
from scripts import reparse_cv


def _parsed(linkedin=None, role="IT Manager Europa"):
    return {
        "full_name": "Rudy Botosso",
        "linkedin": linkedin,
        "skills": ["Python", "SQL"],
        "work_experience": [
            {"role": role, "company": "Hello Nature Group", "start_date": "Ott 2023",
             "end_date": "Mar 2026", "highlights": ["Supportato oltre 15 aziende", "b"]},
        ],
    }


async def _setup(db_session, tmp_path):
    cv = await CVRepository(db_session).create("old.pdf", "old text")
    await CVRepository(db_session).update_parsed_data(cv.id, {"full_name": "Old"})
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"%PDF fake")
    return cv.id, pdf


async def _run(db_session, tmp_path, parsed, **kw):
    cv_id, pdf = await _setup(db_session, tmp_path)
    args = dict(pdf_path=str(pdf), cv_id=cv_id, linkedin=None, dry_run=False, session=db_session)
    args.update(kw)
    with patch.object(reparse_cv, "extract_text", return_value="NEW TEXT"), \
         patch.object(reparse_cv, "parse_cv_with_ollama", new=AsyncMock(return_value=parsed)):
        res = await reparse_cv.reparse(**args)
    return cv_id, res


async def test_dry_run_does_not_modify(db_session, tmp_path):
    cv_id, res = await _run(db_session, tmp_path, _parsed(), dry_run=True)
    cv = await CVRepository(db_session).get_by_id(cv_id)
    assert cv.raw_text == "old text"
    assert json.loads(cv.parsed_data) == {"full_name": "Old"}
    assert res["saved"] is False


async def test_real_run_updates(db_session, tmp_path):
    cv_id, res = await _run(db_session, tmp_path, _parsed())
    cv = await CVRepository(db_session).get_by_id(cv_id)
    assert cv.raw_text == "NEW TEXT"
    data = json.loads(cv.parsed_data)
    assert data["work_experience"][0]["highlights"][0] == "Supportato oltre 15 aziende"
    assert cv.status == "parsed"
    assert res["saved"] is True and res["total_highlights"] == 2


async def test_cli_linkedin_fallback_only_when_empty(db_session, tmp_path):
    _, res = await _run(db_session, tmp_path, _parsed(linkedin=None), linkedin="https://cli")
    assert res["parsed"]["linkedin"] == "https://cli"
    _, res = await _run(db_session, tmp_path, _parsed(linkedin="https://parsed"), linkedin="https://cli")
    assert res["parsed"]["linkedin"] == "https://parsed"


async def test_warning_for_empty_role(db_session, tmp_path):
    _, res = await _run(db_session, tmp_path, _parsed(role=None), dry_run=True)
    assert any(w.startswith("WARNING") for w in res["warnings"])
    assert any("WARNING" in line for line in res["summary"].splitlines())
