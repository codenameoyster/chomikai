import json
import logging
import os
from collections.abc import AsyncGenerator
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from internal import load_env_file

_log = logging.getLogger(__name__)

# Load environment variables from .env file
load_env_file(".env")
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
templates = Jinja2Templates(directory=FRONTEND_DIR)

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
async def login(request: Request) -> Response:
    _log.debug("Login route accessed")
    flow = create_flow()
    # Returns:
    # Tuple[str, str]: The generated authorization URL and state. The
    #     user must visit the URL to complete the flow. The state is used
    #     when completing the flow to verify that the request originated
    #     from your application. If your application is using a different
    #     :class:`Flow` instance to obtain the token, you will need to
    #     specify the ``state`` when constructing the :class:`Flow`.
    auth_info: tuple[str, str] = flow.authorization_url(
        # Recommended, enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    request.session["state"] = auth_info[1]

    return RedirectResponse(url=auth_info[0])


@slides_router.get("/oauth2callback")
async def oauth2_callback(
    request: Request, code: str = "", state: str = "", error: str = ""
) -> Response:
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


def _fetch_thumbnail(file_data: dict[str, Any], credentials: Credentials) -> None:
    slides_service = build(
        "slides", "v1", credentials=credentials, cache_discovery=False
    )

    presentation_id = file_data.get("id")
    _log.debug(f"Processing presentation ID: {presentation_id}")
    if not presentation_id:
        _log.debug("No presentation ID found in file data")
        file_data["thumbnailUrl"] = None
        return None

    try:
        presentation = (
            slides_service.presentations()
            .get(presentationId=presentation_id, fields="slides(objectId)")
            .execute()
        )

        object_id: str | None = presentation.get("slides", [{}])[0].get(
            "objectId", None
        )

        _log.debug(f"object ID: {object_id}")

        if object_id:
            thumbnail_response = (
                slides_service.presentations()
                .pages()
                .getThumbnail(
                    presentationId=presentation_id,
                    pageObjectId=object_id,
                    thumbnailProperties_thumbnailSize="MEDIUM",  # Options: SMALL, MEDIUM, LARGE
                )
                .execute()
            )

            # thumbnailUrl used in the HTML template
            # https://googleapis.github.io/google-api-python-client/docs/dyn/slides_v1.presentations.html - contentUrl
            file_data["thumbnailUrl"] = thumbnail_response.get("contentUrl")
            _log.debug(
                f"Thumbnail URL for presentation {presentation_id}: {file_data['thumbnailUrl']}"
            )
        else:
            file_data["thumbnailUrl"] = None  # No first slide found
            _log.warning(
                f"Could not find first slide ID for presentation {presentation_id}"
            )

    except Exception as e:
        _log.error(f"Error fetching thumbnail for presentation {presentation_id}: {e}")
        file_data["thumbnailUrl"] = None  # Set to None on error


@slides_router.get("/presentations")
async def list_presentations(
    request: Request,
) -> Response:
    _log.debug("Presentations route accessed for SSE")

    credentials_dict = get_credentials_from_session(request)
    if not credentials_dict:
        # Redirect to login if not authenticated
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    # Check if the request accepts text/event-stream, otherwise serve the initial page
    accept_header = request.headers.get("accept", "")
    if "text/event-stream" not in accept_header:
        _log.debug("Serving initial progress HTML page")
        progress_page = os.path.join(FRONTEND_DIR, "progress.html")
        if os.path.exists(progress_page):
            return FileResponse(progress_page)
        else:
            raise HTTPException(status_code=404, detail="Progress page not found")

    # This part runs only if 'text/event-stream' IS in the accept header
    async def event_stream() -> AsyncGenerator[str, None]:
        _log.debug("Starting SSE stream")
        try:
            credentials = Credentials(
                token=credentials_dict["token"],
                refresh_token=credentials_dict["refresh_token"],
                token_uri=credentials_dict["token_uri"],
                client_id=credentials_dict["client_id"],
                client_secret=credentials_dict["client_secret"],
                scopes=credentials_dict["scopes"],
            )
            drive_service = build(
                "drive", "v3", credentials=credentials, cache_discovery=False
            )

            # Query for all presentations
            # https://developers.google.com/workspace/drive/api/guides/mime-types
            query = "mimeType='application/vnd.google-apps.presentation'"
            presentations_data: list[Any] = []

            # Fetch presentations from Drive API
            # we're not using pagination here (nextPageToken) because we fetch up to 1000 files
            list_request = drive_service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name, createdTime, modifiedTime, webViewLink)",
                pageSize=1000,  # Consider pagination for very large numbers
            )
            response = list_request.execute()
            _log.debug(f"Drive API response: {response}")
            files: list[Any] = response.get("files", [])
            total_files = len(files)
            processed_files = 0

            if total_files == 0:
                # Send initial progress if no files
                progress_data = json.dumps({"percent": 100, "processed": 0, "total": 0})
                yield f"event: progress\ndata: {progress_data}\n\n"
            else:
                # Send initial 0% progress
                progress_data = json.dumps(
                    {"percent": 0, "processed": 0, "total": total_files}
                )
                yield f"event: progress\ndata: {progress_data}\n\n"

            with ThreadPoolExecutor(max_workers=15) as executor:
                # Check if there are files before submitting to executor
                if files:
                    futures: dict[Future[None], Any] = {
                        executor.submit(
                            _fetch_thumbnail, file_data, credentials
                        ): file_data
                        for file_data in files
                    }

                    # Iterate over the futures as they complete
                    for future_result in as_completed(futures):
                        processed_files += 1
                        try:
                            # Get the result of the future. This will re-raise any exception
                            # that occurred during the execution of _fetch_thumbnail.
                            future_result.result()  # Wait for thumbnail fetch to complete
                        except Exception as exc:
                            # Handle exceptions from _fetch_thumbnail
                            file_data = futures[future_result]
                            _log.error(
                                f"Fetching thumbnail for file {file_data.get('id')} generated an exception: {exc}"
                            )
                            # Ensure thumbnailUrl is set even if fetching failed
                            if "thumbnailUrl" not in file_data:
                                _log.warning(
                                    f"No thumbnail in the file_data {file_data.get('id')}"
                                )
                                file_data["thumbnailUrl"] = None
                        finally:
                            # Send progress update via SSE regardless of success or failure
                            percent: float | Literal[100] = (
                                (processed_files / total_files) * 100
                                if total_files > 0
                                else 100
                            )
                            progress_data = json.dumps(
                                {
                                    "percent": percent,
                                    "processed": processed_files,
                                    "total": total_files,
                                }
                            )
                            _log.debug(f"Sending progress: {progress_data}")
                            yield f"event: progress\ndata: {progress_data}\n\n"

            # All thumbnails processed (or no files to process)
            _log.debug(f"All thumbnails processed: data {files}")
            presentations_data.extend(files)

            # Render the final HTML content
            # Note: Using the template rendering within the async generator
            # TemplateResponse.body is already bytes, no need to decode
            final_html_bytes: bytes | memoryview[int] = templates.TemplateResponse(
                "presentations.html",
                {"request": request, "presentations": presentations_data},
            ).body
            final_html: str | Any = final_html_bytes.decode("utf-8")

            # Send the complete event with the final HTML
            complete_data = json.dumps({"html": final_html})
            _log.debug("Sending complete event")
            yield f"event: complete\ndata: {complete_data}\n\n"

        except Exception as e:
            _log.error(f"Error during SSE stream: {e}", exc_info=True)
            error_data = json.dumps({"message": f"An error occurred: {e}"})
            yield f"event: error\ndata: {error_data}\n\n"  # Send an error event to the client
        finally:
            _log.debug("SSE stream finished")

    # Return the streaming response (This is outside the 'if' block)
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@slides_router.get("/logout")
async def logout(request: Request) -> dict[str, str]:
    """Clear the session and log out the user."""
    request.session.clear()
    return {"message": "Successfully logged out"}
