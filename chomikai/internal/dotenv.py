"""
Environment variable loading utilities.

This module provides functionality to load environment variables from .env files,
which is essential for managing configuration in the ChomiKAI application.
The loader supports a basic .env file format with key=value pairs and handles
comments and empty lines appropriately.

Features:
- Loads key=value pairs from .env files
- Ignores comments (lines starting with #)
- Strips quotes from values
- Logs loading process for debugging
- Overwrites existing environment variables
"""

import logging
import os

_log = logging.getLogger(__name__)


def load_env_file(env_path: str = ".env") -> None:
    """
    Load environment variables from an .env file.

    Reads a .env file and loads all key=value pairs into the environment.
    Lines starting with # are treated as comments and ignored. Empty lines
    are also ignored. Values can be quoted with single or double quotes.

    Args:
        env_path: Path to the .env file to load. Defaults to ".env".

    Raises:
        FileNotFoundError: If the specified .env file doesn't exist.
        ValueError: If a line doesn't contain a valid key=value pair.

    Example:
        # .env file content:
        GOOGLE_CLIENT_ID=your_client_id
        GOOGLE_CLIENT_SECRET="your_secret"
        # This is a comment

        # Usage:
        load_env_file(".env")
    """
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            _log.debug(f"Loading environment variable: {key.strip()} = {value.strip()}")
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
            _log.info(f"Loaded environment variable: {key.strip()}")
