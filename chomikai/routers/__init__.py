"""
Router module for ChomiKAI application.

This module provides FastAPI routers for handling various HTTP endpoints.
Currently includes authentication and Google Slides integration routes.

Exports:
    slides_router: APIRouter instance for Google Slides authentication and presentation management
"""

# Import exceptions for easier access
from .auth import slides_router

__all__ = ["slides_router"]
