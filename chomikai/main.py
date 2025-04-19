import logging
import secrets

import uvicorn
from fastapi import FastAPI
from routers import slides_router
from starlette.middleware.sessions import SessionMiddleware

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

app = FastAPI(title="Google Slides API Integration")

app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_urlsafe(32),
)

app.include_router(router=slides_router)

# Run the application
if __name__ == "__main__":
    _log.debug("Starting FastAPI application")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")
