"""
google_auth.py — Shared Google API credential helper
Place at: ~/.claude/skills/google_auth.py

Used by Claude Code skills that need Gmail or Drive access.
Loads token.json from ~/.config/home-automation/token.json,
auto-refreshes if expired. No interactive login needed.

To generate token.json, run:
    python3 ~/devel/home-automation/authorize.py
"""

import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_PATH = os.path.expanduser("~/.config/home-automation/token.json")


# Must match the scopes requested in authorize.py
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
]


def _load_creds() -> Credentials:
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(
            f"token.json not found at {TOKEN_PATH}. "
            "Run authorize.py to generate it."
        )
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def get_gmail():
    """Returns an authenticated Gmail API client."""
    return build("gmail", "v1", credentials=_load_creds())


def get_drive():
    """Returns an authenticated Google Drive API client."""
    return build("drive", "v3", credentials=_load_creds())

