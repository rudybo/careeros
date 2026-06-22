import pytest

from app.services.cv_extractor import UnsupportedFileTypeError, extract_text


def test_unsupported_extension_raises():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text("cv.txt", b"some content")


def test_unsupported_extension_xlsx_raises():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text("cv.xlsx", b"some content")


def test_invalid_pdf_content_raises():
    from app.services.cv_extractor import CVExtractionError
    with pytest.raises(CVExtractionError):
        extract_text("cv.pdf", b"not a real pdf")


def test_invalid_docx_content_raises():
    from app.services.cv_extractor import CVExtractionError
    with pytest.raises(CVExtractionError):
        extract_text("cv.docx", b"not a real docx")
