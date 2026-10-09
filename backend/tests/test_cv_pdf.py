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


def _text_pages(pdf: bytes):
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return "\n".join(p.extract_text() or "" for p in doc.pages), len(doc.pages), doc


def _big_cv() -> ParsedCV:
    long = "Sviluppo e manutenzione di servizi backend distribuiti con attenzione a qualità e prestazioni. " * 3
    exps = [WorkExperience(company=f"Azienda{i}", role=f"Ruolo{i}", start_date="2015", end_date="2020",
                           description=long,
                           highlights=[f"Risultato {i}.{j} " + "ottenuto con grande impegno e metodo " * 2
                                       for j in range(5)]) for i in range(5)]
    return ParsedCV(full_name="Rudy Botosso", email="r@x.it", phone="1", location="Milano",
                    linkedin="https://linkedin.com/in/rudybotosso", summary=long,
                    skills=["Python", "SQL"] * 8, work_experience=exps,
                    education=[Education(institution="Uni", degree="Laurea")], languages=["Italiano"])


def test_big_cv_fits_one_page():
    text, n, _ = _text_pages(render_cv_pdf(_big_cv()))
    assert n == 1
    assert "Azienda4" in text and "Risultato 0.0" in text


def test_short_cv_one_page_and_base_font_size():
    pdf = render_cv_pdf(_big_cv().model_copy(update={"work_experience": _big_cv().work_experience[:1]}))
    _, n, doc = _text_pages(pdf)
    assert n == 1
    sizes = {round(c["size"], 1) for c in doc.pages[0].chars if c["text"] == "S"}
    assert 9.5 in sizes


def test_linkedin_text_link_and_bullets():
    text, _, doc = _text_pages(render_cv_pdf(_big_cv()))
    assert "https://linkedin.com/in/rudybotosso" in text
    assert doc.pages[0].hyperlinks or doc.pages[0].annots
    assert "•" in text


def test_period_edge_cases():
    def head(**kw):
        cv = ParsedCV(full_name="A B", work_experience=[WorkExperience(company="Acme", role="Dev", **kw)])
        return _text_pages(render_cv_pdf(cv))[0]
    assert "Dev — Acme" in head() and "(" not in head()
    assert "presente" not in head()
    assert "fino a 2020" in head(end_date="2020")
    assert "2021 – presente" in head(start_date="2021")
    assert "2019 – 2020" in head(start_date="2019", end_date="2020")


_PROJ = ["81-Flow: piattaforma multi-azienda sviluppata in Python con NiceGUI e PostgreSQL per un cliente. " * 2,
         "CareerOS: applicazione web in Python che con 4 agenti AI aiuta la ricerca del lavoro. " * 2]


def test_projects_section_printed_between_experience_and_education():
    cv = _big_cv().model_copy(update={"work_experience": _big_cv().work_experience[:1], "projects": _PROJ})
    text, n, _ = _text_pages(render_cv_pdf(cv))
    assert n == 1 and "PROGETTI PERSONALI" in text
    assert "81-Flow:" in text and "CareerOS:" in text
    assert text.index("ESPERIENZA") < text.index("PROGETTI PERSONALI") < text.index("FORMAZIONE")


def test_no_projects_no_heading():
    text, _, _ = _text_pages(render_cv_pdf(_big_cv()))
    assert "PROGETTI PERSONALI" not in text


def test_big_cv_with_projects_still_one_page():
    cv = _big_cv().model_copy(update={"projects": _PROJ})
    _, n, _ = _text_pages(render_cv_pdf(cv))
    assert n == 1


def test_trim_step_drops_projects_first():
    from app.services.cv_pdf import _trim_step
    cv = _big_cv().model_copy(update={"projects": _PROJ + ["Terzo: x"]}, deep=True)
    hl = [len(e.highlights) for e in cv.work_experience]
    assert _trim_step(cv) and len(cv.projects) == 2
    assert _trim_step(cv) and len(cv.projects) == 1
    assert _trim_step(cv) and cv.projects == []
    assert [len(e.highlights) for e in cv.work_experience] == hl
    assert _trim_step(cv) and sum(len(e.highlights) for e in cv.work_experience) == sum(hl) - 1


# --- sanitizzazione unicode e filler ---
def _txt(cv):
    t, _, _ = _text_pages(render_cv_pdf(cv))
    return t


def _bad(t):
    return any(x in t for x in ("■", "�", "(cid:"))


def test_unicode_hyphens_and_spaces_rendered_as_ascii():
    cv = ParsedCV(full_name="Rudy Botosso", linkedin="https://linkedin.com/in/rudy-b",
                  summary="Visione end‑to‑end e decision‐making​.",
                  work_experience=[WorkExperience(company="Acme", role="Dev", start_date="2020", end_date="2021",
                                                  highlights=["Analisi end‑to‑end tecnico‑economica",
                                                              "Post‐acquisizione ok − fine"])])
    t = _txt(cv)
    assert "end-to-end" in t and "tecnico-economica" in t and "decision-making" in t
    assert not _bad(t)
    assert "linkedin.com/in/rudy-b" in t


def test_emoji_and_cjk_dropped_without_crash():
    cv = ParsedCV(full_name="Rudy", summary="Ottimo 🚀 lavoro 中文 café",
                  skills=["Python 🐍"])
    t = _txt(cv)
    assert "Ottimo" in t and "lavoro" in t and "café" in t
    assert not _bad(t)


def test_filler_values_skipped_in_education_certs_languages():
    cv = ParsedCV(full_name="Rudy",
                  education=[Education(institution="Various", degree="Corso Data Analyst con Excel e Python",
                                       field="N/A", year="2026"),
                             Education(institution="Unknown", degree="-")],
                  certifications=["Varie", "AWS Cloud"], languages=["Italiano", "N/A", "none"])
    t = _txt(cv)
    assert "Corso Data Analyst con Excel e Python, 2026" in t
    for w in ("Various", "N/A", "Unknown", "Varie", "none"):
        assert w not in t
    assert "AWS Cloud" in t and "Italiano" in t


def test_trim_drops_highlights_and_descriptions_before_whole_experiences():
    from app.services.cv_pdf import _trim_step
    cv = _big_cv()
    while _trim_step(cv):
        if len(cv.work_experience) < 5:
            break
    assert all(not e.highlights and not e.description for e in cv.work_experience)
