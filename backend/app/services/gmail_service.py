"""Gmail API service — draft creation and label management."""
import base64
import logging
import os
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CREDENTIALS_FILE = Path(__file__).parent.parent.parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent.parent.parent / "token.json"
LABEL_NAME = "CareerOS"


def get_gmail_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError("Gmail non autenticato. Esegui prima: python setup_gmail.py")
        TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _get_or_create_label(service) -> str:
    """Return the label ID for 'CareerOS', creating it if needed."""
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for lbl in labels:
        if lbl["name"] == LABEL_NAME:
            return lbl["id"]
    new_label = service.users().labels().create(
        userId="me",
        body={"name": LABEL_NAME, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    ).execute()
    logger.info("Label '%s' creata: %s", LABEL_NAME, new_label["id"])
    return new_label["id"]


def create_draft(to: str, subject: str, body: str) -> dict:
    """Create a Gmail draft in the CareerOS label. Returns {'draft_id', 'gmail_url'}."""
    service = get_gmail_service()
    label_id = _get_or_create_label(service)

    message = MIMEText(body, "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw}},
    ).execute()

    draft_id = draft["id"]
    message_id = draft.get("message", {}).get("id", "")

    # Apply CareerOS label to the draft message
    if message_id and label_id:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()

    gmail_url = f"https://mail.google.com/mail/u/0/#drafts/{message_id}" if message_id else "https://mail.google.com/mail/u/0/#drafts"
    logger.info("Bozza creata: draft_id=%s label=%s", draft_id, LABEL_NAME)
    return {"draft_id": draft_id, "gmail_url": gmail_url}
