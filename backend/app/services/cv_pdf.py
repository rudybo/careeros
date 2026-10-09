"""Rendering PDF di un ParsedCV (ReportLab)."""
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from app.schemas.cv import ParsedCV

_ss = getSampleStyleSheet()
_NAME = ParagraphStyle("name", parent=_ss["Title"], fontSize=20, leading=24, alignment=0, spaceAfter=2)
_CONTACT = ParagraphStyle("contact", parent=_ss["Normal"], fontSize=9, textColor=colors.HexColor("#555555"))
_H = ParagraphStyle("h", parent=_ss["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=2,
                    textColor=colors.HexColor("#1f3a5f"))
_BODY = ParagraphStyle("body", parent=_ss["Normal"], fontSize=9.5, leading=13)
_JOB = ParagraphStyle("job", parent=_BODY, fontName="Helvetica-Bold", spaceBefore=4)


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _section(story: list, title: str) -> None:
    story.append(_p(title.upper(), _H))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#c8d0da")))
    story.append(Spacer(1, 3))


def render_cv_pdf(cv: ParsedCV) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=f"CV {cv.full_name}",
                            author=cv.full_name)
    story: list = [_p(cv.full_name, _NAME)]
    contact = " · ".join(x for x in (cv.email, cv.phone, cv.location) if x)
    if contact:
        story.append(_p(contact, _CONTACT))

    if cv.summary:
        _section(story, "Profilo")
        story.append(_p(cv.summary, _BODY))
    if cv.skills:
        _section(story, "Competenze")
        story.append(_p(", ".join(cv.skills), _BODY))
    if cv.work_experience:
        _section(story, "Esperienza professionale")
        for e in cv.work_experience:
            period = f"{e.start_date or ''} – {e.end_date or 'presente'}".strip(" –")
            head = " — ".join(x for x in (e.role, e.company) if x)
            story.append(_p(f"{head}  ({period})" if period else head, _JOB))
            if e.description:
                story.append(_p(e.description, _BODY))
    if cv.education:
        _section(story, "Formazione")
        for ed in cv.education:
            line = ", ".join(x for x in (ed.degree, ed.field, ed.institution, ed.year) if x)
            story.append(_p(line, _BODY))
    if cv.languages:
        _section(story, "Lingue")
        story.append(_p(", ".join(cv.languages), _BODY))
    if cv.certifications:
        _section(story, "Certificazioni")
        story.append(_p(", ".join(cv.certifications), _BODY))

    doc.build(story)
    return buf.getvalue()
