"""
ChomiKAI - Google Slides Integration Application.

This is the main FastAPI application that provides a web interface for Google Slides
authentication and presentation management. The application serves as a bridge between
users and Google's APIs, offering real-time presentation listing with thumbnails.

Key Features:
- FastAPI web framework with async support
- Google OAuth2 authentication flow
- Session-based credential management
- CORS middleware for cross-origin requests
- Real-time progress updates via Server-Sent Events
- Google Slides and Drive API integration

The application includes:
- Authentication routes for Google OAuth2
- Presentation listing with thumbnail generation
- Session management for user credentials
- Static file serving for frontend assets

Usage:
    Run directly: python main.py
    Or with uvicorn: uvicorn main:app --reload

Environment Requirements:
- GOOGLE_CLIENT_ID: Google OAuth2 client ID
- GOOGLE_CLIENT_SECRET: Google OAuth2 client secret
- GOOGLE_PROJECT_ID: Google Cloud project ID
"""

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
