from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.settings import settings

_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def get_gmail_service():
    """
    FastAPI dependency — builds an authenticated Gmail API service.

    Reads OAuth2 credentials from the path configured in settings.GMAIL_TOKEN_PATH.
    Refreshes the access token automatically if it has expired.
    """
    try:
        creds = Credentials.from_authorized_user_file(settings.GMAIL_TOKEN_PATH, _SCOPES)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=f"Gmail token file not found at '{settings.GMAIL_TOKEN_PATH}'",
        )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)
