import base64
import email
from unittest.mock import MagicMock, patch

from app.services import gmail_service


def test_build_message_plain_without_attachments():
    msg = gmail_service._build_message("", "Oggetto", "Corpo")
    assert not msg.is_multipart()
    assert msg["to"] is None
    assert msg["subject"] == "Oggetto"


def test_build_message_with_pdf_attachment():
    msg = gmail_service._build_message("hr@acme.it", "Ogg", "Corpo", [("CV.pdf", b"%PDF-1.4 x")])
    assert msg.is_multipart() and msg["to"] == "hr@acme.it"
    parts = list(msg.walk())
    pdf = next(p for p in parts if p.get_filename() == "CV.pdf")
    assert pdf.get_content_type() == "application/pdf"
    assert pdf.get_payload(decode=True) == b"%PDF-1.4 x"
    body = next(p for p in parts if p.get_content_type() == "text/plain")
    assert body.get_payload(decode=True).decode("utf-8") == "Corpo"


def test_create_draft_sends_raw_with_attachment():
    service = MagicMock()
    service.users().labels().list().execute.return_value = {"labels": [{"name": "CareerOS", "id": "L1"}]}
    service.users().drafts().create().execute.return_value = {"id": "D1", "message": {"id": "M1"}}
    with patch.object(gmail_service, "get_gmail_service", return_value=service):
        res = gmail_service.create_draft("", "Ogg", "Corpo", [("CV.pdf", b"%PDF")])
    assert res["draft_id"] == "D1" and "M1" in res["gmail_url"]
    body = service.users().drafts().create.call_args.kwargs["body"]
    raw = base64.urlsafe_b64decode(body["message"]["raw"])
    parsed = email.message_from_bytes(raw)
    assert any(p.get_filename() == "CV.pdf" for p in parsed.walk())
