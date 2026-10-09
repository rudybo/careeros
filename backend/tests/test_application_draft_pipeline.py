from unittest.mock import AsyncMock, patch

from app.agents.job_parser.agent import JobMeta
from app.schemas.cv import ParsedCV, WorkExperience
from app.services import application_draft

CV = ParsedCV(full_name="Rudy Botosso",
              work_experience=[WorkExperience(company="Acme", role="Dev", description="x")])


async def test_build_tailored_draft_wires_everything():
    tailored = CV.model_copy(deep=True)
    letter = {"subject": "Candidatura per il ruolo di Dev - Rudy Botosso", "full_text": "testo lettera"}
    with patch.object(application_draft.job_parser, "parse",
                      new=AsyncMock(return_value=JobMeta(advertiser_type="recruiter"))) as parse, \
         patch.object(application_draft.cv_tailor, "tailor", new=AsyncMock(return_value=tailored)), \
         patch.object(application_draft.cover_letter_agent, "generate", new=AsyncMock(return_value=letter)) as gen, \
         patch.object(application_draft, "render_cv_pdf", return_value=b"%PDF-x"), \
         patch.object(application_draft.gmail_service, "create_draft",
                      return_value={"draft_id": "D1", "gmail_url": "https://g/D1"}) as draft:
        res = await application_draft.build_tailored_draft(
            CV, "Acme", "Dev", "annuncio scrivi a hr@acme.it", advertiser_type=None, contact_email=None)

    parse.assert_awaited_once()
    assert gen.await_args.kwargs["advertiser_type"] == "recruiter"
    kwargs = draft.call_args.kwargs
    assert kwargs["to"] == "hr@acme.it" and kwargs["subject"] == letter["subject"]
    assert kwargs["attachments"][0][1] == b"%PDF-x" and kwargs["attachments"][0][0].endswith(".pdf")
    assert res["draft_id"] == "D1" and res["advertiser_type"] == "recruiter"
    assert res["contact_email"] == "hr@acme.it"
    assert res["pdf_bytes"] == b"%PDF-x" and res["pdf_filename"] == kwargs["attachments"][0][0]


async def test_build_tailored_draft_skips_detection_when_known():
    with patch.object(application_draft.job_parser, "parse", new=AsyncMock()) as parse, \
         patch.object(application_draft.cv_tailor, "tailor", new=AsyncMock(return_value=CV)), \
         patch.object(application_draft.cover_letter_agent, "generate",
                      new=AsyncMock(return_value={"subject": "s", "full_text": "t"})), \
         patch.object(application_draft, "render_cv_pdf", return_value=b"%PDF"), \
         patch.object(application_draft.gmail_service, "create_draft",
                      return_value={"draft_id": "D", "gmail_url": "u"}):
        res = await application_draft.build_tailored_draft(
            CV, "Acme", "Dev", "jd", advertiser_type="direct", contact_email="a@b.it")
    parse.assert_not_awaited()
    assert res["advertiser_type"] == "direct" and res["contact_email"] == "a@b.it"


def test_pdf_filename_normalizes_case():
    assert application_draft._pdf_filename("RUDY BOTOSSO") == "CV_Rudy_Botosso.pdf"
    assert application_draft._pdf_filename("rudy botosso") == "CV_Rudy_Botosso.pdf"
    assert application_draft._pdf_filename("Mario McDonald") == "CV_Mario_McDonald.pdf"
    assert application_draft._pdf_filename("") == "CV_CV.pdf"
