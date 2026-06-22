import io
from pathlib import Path

import ftfy
import pdfplumber
from docx import Document


SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


class UnsupportedFileTypeError(Exception):
    pass


class CVExtractionError(Exception):
    pass


def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Formato '{extension}' non supportato. Usa PDF o DOCX."
        )

    if extension == ".pdf":
        raw = _extract_from_pdf(content)
    else:
        raw = _extract_from_docx(content)

    return ftfy.fix_text(raw)


def _extract_from_pdf(content: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
            text = "\n".join(pages).strip()

        if not text:
            raise CVExtractionError("Il PDF non contiene testo estraibile.")

        return text
    except CVExtractionError:
        raise
    except Exception as e:
        raise CVExtractionError(f"Errore durante l'estrazione del PDF: {e}") from e


def _extract_from_docx(content: bytes) -> str:
    try:
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs).strip()

        if not text:
            raise CVExtractionError("Il DOCX non contiene testo estraibile.")

        return text
    except CVExtractionError:
        raise
    except Exception as e:
        raise CVExtractionError(f"Errore durante l'estrazione del DOCX: {e}") from e
