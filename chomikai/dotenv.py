import logging
import os

_log = logging.getLogger(__name__)


def load_env_file(env_path: str = ".env") -> None:
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            _log.debug(f"Loading environment variable: {key.strip()} = {value.strip()}")
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
            _log.info(f"Loaded environment variable: {key.strip()}")
