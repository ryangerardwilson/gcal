from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import AccountConfig, token_file_for_email
from .errors import ApiError
from .paths import ensure_dirs

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

TRANSCRIPT_SCOPES = [
    *CALENDAR_SCOPES,
    "https://www.googleapis.com/auth/drive.meet.readonly",
]


@dataclass(slots=True)
class AuthorizedAccount:
    credentials: object
    email: str


def authorize_account(client_secret_file: Path, scopes: list[str]) -> AuthorizedAccount:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    ensure_dirs()
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes)
    credentials = flow.run_local_server(port=0)
    oauth_service = build("oauth2", "v2", credentials=credentials, cache_discovery=False)
    user_info = oauth_service.userinfo().get().execute()
    email = str(user_info.get("email", "")).strip().lower()
    if not email:
        raise ApiError("Authorized Google account email could not be determined.")
    token_path = token_file_for_email(email)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return AuthorizedAccount(credentials=credentials, email=email)


def load_credentials(account: AccountConfig, scopes: list[str]):
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError
    from google.oauth2.credentials import Credentials

    ensure_dirs()
    token_path = token_file_for_email(account.email)
    credentials = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
    if credentials and not credentials.has_scopes(scopes):
        credentials = None
    if credentials and credentials.valid:
        return credentials
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except RefreshError:
            credentials = None
        else:
            if credentials.has_scopes(scopes):
                token_path.write_text(credentials.to_json(), encoding="utf-8")
                return credentials
            credentials = None
    if not account.client_secret_file.exists():
        raise ApiError(f"Missing client secret file: {account.client_secret_file}")
    authorized = authorize_account(account.client_secret_file, scopes)
    if authorized.email != account.email:
        raise ApiError(
            f"Authorized account email `{authorized.email}` does not match preset email `{account.email}`. Re-run `gcal auth` for this account."
        )
    return authorized.credentials


def build_calendar_service(account: AccountConfig):
    from googleapiclient.discovery import build

    credentials = load_credentials(account, CALENDAR_SCOPES)
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def build_drive_service(account: AccountConfig):
    from googleapiclient.discovery import build

    credentials = load_credentials(account, TRANSCRIPT_SCOPES)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)
