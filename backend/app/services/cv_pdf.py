"""Rendering PDF di un ParsedCV (ReportLab)."""
import io
import logging
import os
import unicodedata
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from app.schemas.cv import ParsedCV

logger = logging.getLogger(__name__)

# Il bullet "•" di Helvetica (Type1) non e' estraibile dai parser ATS ((cid:127)): lo disegniamo
# con Vera (TTF incluso in ReportLab, embedded con ToUnicode) solo per quel glifo.
pdfmetrics.registerFont(TTFont("Vera", os.path.join(os.path.dirname(reportlab.__file__), "fonts", "Vera.ttf")))

_ss = getSampleStyleSheet()
_SCALES = (1.0, 0.94, 0.88, 0.82, 0.76)
_LINK_COLOR = "#1f3a5f"


class _Styles:
    def __init__(self, k: float) -> None:
        self.name = ParagraphStyle("name", parent=_ss["Title"], fontSize=20 * k, leading=24 * k,
                                   alignment=0, spaceAfter=2 * k)
        self.contact = ParagraphStyle("contact", parent=_ss["Normal"], fontSize=9 * k, leading=11.5 * k,
                                      textColor=colors.HexColor("#555555"))
        self.h = ParagraphStyle("h", parent=_ss["Heading2"], fontSize=11 * k, leading=13 * k,
                                spaceBefore=8 * k, spaceAfter=2 * k, textColor=colors.HexColor("#1f3a5f"))
        self.body = ParagraphStyle("body", parent=_ss["Normal"], fontSize=9.5 * k, leading=12.2 * k)
        self.job = ParagraphStyle("job", parent=self.body, fontName="Helvetica-Bold", spaceBefore=3 * k)
        self.bullet = ParagraphStyle("bullet", parent=self.body, leftIndent=12 * k, bulletIndent=2 * k,
                                     bulletFontName="Vera")
        self.gap = 3 * k


_DASHES = {"‐": "-", "‑": "-", "‒": "-", "−": "-"}
_ZERO_WIDTH = {"​", "‌", "‍", "⁠", "﻿", "­"}
_FILLER = {"various", "n/a", "na", "none", "null", "-", "—", "unknown", "varie", "vari"}


def _cp1252_ok(ch: str) -> bool:
    try:
        ch.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def _clean(text: str | None) -> str:
    """Rende il testo disegnabile da Helvetica (cp1252): mappa trattini/spazi unicode, scarta il resto."""
    out: list[str] = []
    for ch in text or "":
        if ch in _DASHES:
            out.append(_DASHES[ch])
        elif ch in _ZERO_WIDTH:
            continue
        elif ch in "\n\t":
            out.append(ch)
        elif unicodedata.category(ch) in ("Zs", "Zl", "Zp"):
            out.append(" ")
        elif unicodedata.category(ch) in ("Cc", "Cf"):
            continue
        elif _cp1252_ok(ch):
            out.append(ch)
        else:
            out.extend(c for c in unicodedata.normalize("NFKD", ch)
                       if not unicodedata.combining(c) and _cp1252_ok(c))
    return "".join(out)


def _real(value: str | None) -> str:
    v = (value or "").strip()
    return "" if v.lower() in _FILLER else v


def _p(text: str, style: ParagraphStyle, **kw) -> Paragraph:
    return Paragraph(escape(_clean(text)).replace("\n", "<br/>"), style, **kw)


def _section(story: list, title: str, st: _Styles) -> None:
    story.append(_p(title.upper(), st.h))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#c8d0da")))
    story.append(Spacer(1, st.gap))


def _period(start: str | None, end: str | None) -> str:
    if start and end:
        return f"{start} – {end}"
    if start:
        return f"{start} – presente"
    if end:
        return f"fino a {end}"
    return ""


def _linkedin_para(url: str, st: _Styles) -> Paragraph:
    href = url if "://" in url else f"https://{url}"
    return Paragraph(f'<a href={quoteattr(href)} color="{_LINK_COLOR}">{escape(_clean(url))}</a>', st.contact)


def _project_markup(text: str) -> str:
    """Prefisso "Nome:" in grassetto (solo se breve), resto testo normale."""
    text = _clean(text)
    name, sep, rest = text.partition(": ")
    if sep and 0 < len(name) <= 40 and "\n" not in name:
        return f"<b>{escape(name)}:</b> {escape(rest)}"
    return escape(text).replace("\n", "<br/>")


def _experience_section(story: list, title: str, exps: list, st: _Styles) -> None:
    if not exps:
        return
    _section(story, title, st)
    for e in exps:
        period = _period(e.start_date, e.end_date)
        head = " — ".join(x for x in (e.role, e.company) if x)
        story.append(_p(f"{head}  ({period})" if period else head, st.job))
        if e.description:
            story.append(_p(e.description, st.body))
        for h in e.highlights:
            story.append(_p(h, st.bullet, bulletText="•"))


def _build(cv: ParsedCV, k: float) -> tuple[bytes, int]:
    st = _Styles(k)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=f"CV {cv.full_name}",
                            author=cv.full_name)
    story: list = [_p(cv.full_name, st.name)]
    contact = " · ".join(x for x in (cv.email, cv.phone, cv.location) if x)
    if contact:
        story.append(_p(contact, st.contact))
    if cv.linkedin:
        story.append(_linkedin_para(cv.linkedin, st))

    if cv.summary:
        _section(story, "Profilo", st)
        story.append(_p(cv.summary, st.body))
    if cv.skills:
        _section(story, "Competenze", st)
        story.append(_p(", ".join(cv.skills), st.body))
    _experience_section(story, "Esperienza professionale", cv.work_experience, st)
    _experience_section(story, "Altre esperienze", cv.other_experience, st)
    if cv.projects:
        _section(story, "Progetti personali", st)
        for proj in cv.projects:
            story.append(Paragraph(_project_markup(proj), st.bullet, bulletText="•"))
    if cv.education:
        _section(story, "Formazione", st)
        for ed in cv.education:
            line = ", ".join(x for x in map(_real, (ed.degree, ed.field, ed.institution, ed.year)) if x)
            if line:
                story.append(_p(line, st.body))
    languages = [x for x in map(_real, cv.languages) if x]
    if languages:
        _section(story, "Lingue", st)
        story.append(_p(", ".join(languages), st.body))
    certs = [x for x in map(_real, cv.certifications) if x]
    if certs:
        _section(story, "Certificazioni", st)
        story.append(_p(", ".join(certs), st.body))

    doc.build(story)
    return buf.getvalue(), doc.page


def _trim_step(cv: ParsedCV) -> bool:
    """Riduce il contenuto di un passo (in place). False se non resta nulla da togliere."""
    if len(cv.projects) > 1:
        cv.projects.pop()
        return True
    if cv.projects:
        cv.projects.clear()
        return True
    # Prima si asciugano le "Altre esperienze", poi quelle principali; esperienze intere per ultime.
    for lst in (cv.other_experience, cv.work_experience):
        for e in reversed(lst):
            if len(e.highlights) > 1:
                e.highlights.pop()
                return True
        for e in reversed(lst):
            if e.highlights:
                e.highlights.clear()
                return True
        for e in reversed(lst):
            if e.description:
                e.description = None
                return True
    if cv.other_experience:
        cv.other_experience.pop()
        return True
    if len(cv.work_experience) > 1:
        cv.work_experience.pop()
        return True
    return False


def render_cv_pdf(cv: ParsedCV) -> bytes:
    """Genera il PDF garantendo UNA sola pagina (riduce font, poi toglie bullet dalle ultime esperienze)."""
    work = cv.model_copy(deep=True)
    trimmed = False
    while True:
        for k in _SCALES:
            pdf, pages = _build(work, k)
            if pages <= 1:
                if trimmed:
                    logger.warning("CV PDF: contenuto ridotto per stare in una pagina (scala %.2f)", k)
                return pdf
        trimmed = True
        if not _trim_step(work):
            logger.warning("CV PDF: impossibile stare in una pagina, output su %d pagine", pages)
            return pdf
