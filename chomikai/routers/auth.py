import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow  # type: ignore
from googleapiclient.discovery import build
from internal import load_env_file

_log = logging.getLogger(__name__)

# Load environment variables from .env file
load_env_file(".env")
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

slides_router = APIRouter()

# OAuth2 configuration
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/presentations.readonly",
]
REDIRECT_URI = "http://localhost:8000/oauth2callback"

client_config: dict[str, dict[str, Any]] = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI],
    }
}


def create_flow() -> Flow:
    _log.debug("Creating OAuth2 flow")
    return Flow.from_client_config(  # type: ignore
        client_config=client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def get_credentials_from_session(request: Request) -> Any | None:
    _log.debug("Retrieving credentials from session")
    if "credentials" in request.session:
        return request.session["credentials"]

    _log.warning("No credentials found in session")
    return None


@slides_router.get("/")
async def index():
    _log.debug("Index route accessed")
    login_page = os.path.join(FRONTEND_DIR, "login.html")
    if os.path.exists(login_page):
        return FileResponse(login_page)
    else:
        return {
            "message": "Welcome to the Google Slides API Integration!",
            "authenticate": "visit /login",
        }


@slides_router.get("/login")
async def login(request: Request):
    _log.debug("Login route accessed")
    flow = create_flow()
    authorization_url, state = flow.authorization_url(  # type: ignore
        # Recommended, enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    request.session["state"] = state

    return RedirectResponse(url=authorization_url)


@slides_router.get("/oauth2callback")
async def oauth2_callback(
    request: Request, code: str = "", state: str = "", error: str = ""
):
    _log.debug("OAuth2 callback route accessed")
    if len(error) > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    if state != request.session.get("state"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="State mismatch"
        )

    flow = create_flow()
    flow.fetch_token(code=code)

    request.session["credentials"] = {
        "token": flow.credentials.token,
        "refresh_token": flow.credentials.refresh_token,
        "token_uri": flow.credentials.token_uri,
        "client_id": flow.credentials.client_id,
        "client_secret": flow.credentials.client_secret,
        "scopes": flow.credentials.scopes,
    }

    return RedirectResponse(url="/presentations")


@slides_router.get("/presentations")
async def list_presentations(request: Request):
    _log.debug("Presentations route accessed")

    credentials_dict = get_credentials_from_session(request)
    if not credentials_dict:
        # Redirect to login if not authenticated
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    credentials = Credentials(
        token=credentials_dict["token"],
        refresh_token=credentials_dict["refresh_token"],
        token_uri=credentials_dict["token_uri"],
        client_id=credentials_dict["client_id"],
        client_secret=credentials_dict["client_secret"],
        scopes=credentials_dict["scopes"],
    )
    drive_service = build("drive", "v3", credentials=credentials)
    # Query for all presentations
    query = "mimeType='application/vnd.google-apps.presentation'"

    presentations: list[Any] = []
    page_token: str = ""

    while True:
        response = (
            drive_service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, createdTime, modifiedTime, webViewLink)",
                pageToken=page_token,
            )
            .execute()
        )

        presentations.extend(response.get("files", []))
        page_token = response.get("nextPageToken", "")
        if page_token == "":
            break

    return presentations


@slides_router.get("/logout")
async def logout(request: Request):
    """Clear the session and log out the user."""
    request.session.clear()
    return {"message": "Successfully logged out"}
