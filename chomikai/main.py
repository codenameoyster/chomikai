import logging
import secrets

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import slides_router
from starlette.middleware.sessions import SessionMiddleware

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

app = FastAPI(title="Google Slides API Integration")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",  # Allow your frontend origin
        "https://lh7-us.googleusercontent.com",  # Allow Google's thumbnail domain
        # Add other origins if needed
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_urlsafe(32),
)

app.include_router(router=slides_router)

# Run the application
if __name__ == "__main__":
    _log.debug("Starting FastAPI application")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")
