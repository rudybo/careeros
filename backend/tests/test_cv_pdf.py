import io

import pdfplumber

from app.schemas.cv import Education, ParsedCV, WorkExperience
from app.services.cv_pdf import render_cv_pdf


def test_render_pdf_contains_content():
    cv = ParsedCV(
        full_name="Rudy Botosso", email="r@x.it", phone="123", location="Milano",
        summary="Sviluppatore <backend> & API.",
        skills=["Python", "FastAPI"],
        work_experience=[WorkExperience(company="Acme", role="Backend Developer",
                                        start_date="2022", end_date=None, description="Sviluppo API REST.")],
        education=[Education(institution="Uni Milano", degree="Laurea", field="Informatica", year="2019")],
        languages=["Italiano"], certifications=[],
    )
    pdf = render_cv_pdf(cv)
    assert pdf.startswith(b"%PDF")
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = "\n".join(p.extract_text() or "" for p in doc.pages)
    assert "Rudy Botosso" in text and "Acme" in text and "FastAPI" in text
    assert "<backend> & API" in text  # caratteri speciali escapati correttamente


def test_render_pdf_minimal_cv():
    assert render_cv_pdf(ParsedCV(full_name="Solo Nome")).startswith(b"%PDF")
