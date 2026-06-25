"""
Run once to authenticate CareerOS with Gmail.
Opens the browser for OAuth consent, then saves token.json.

Usage:
    cd backend
    python setup_gmail.py
"""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"

if not CREDENTIALS_FILE.exists():
    print("ERROR: credentials.json non trovato in backend/")
    exit(1)

flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
creds = flow.run_local_server(port=0, open_browser=True)
TOKEN_FILE.write_text(creds.to_json())
print(f"\nAutenticazione completata! Token salvato in: {TOKEN_FILE}")
print("Ora puoi avviare il backend normalmente.")
