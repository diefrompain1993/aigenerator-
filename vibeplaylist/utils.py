"""Utility functions for logging and helper routines."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure application-wide logging.

    Parameters
    ----------
    level: int
        Logging level to apply for the root logger.
    """

    logging.basicConfig(level=level, format=LOG_FORMAT)
    logging.getLogger(__name__).debug("Logging has been configured", extra={"level": level})


def load_json(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Load a JSON file from disk with fallback to a default value."""

    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError) as error:  # pragma: no cover - defensive
        logging.getLogger(__name__).warning("Failed to load %s: %s", path, error)
        return default


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    """Persist a JSON payload to disk."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except OSError as error:  # pragma: no cover - defensive
        logging.getLogger(__name__).warning("Failed to save %s: %s", path, error)


def resolve_token() -> str | None:
    """Return Yandex Music token from environment or a local cache file."""

    env_token = os.getenv("YANDEX_MUSIC_TOKEN")
    if env_token:
        return env_token

    cache_path = Path.home() / ".config" / "vibeplaylist" / "token.json"
    cached = load_json(cache_path, {})
    token = cached.get("token")
    return token


def cache_token(token: str) -> None:
    """Persist the Yandex Music token for reuse across sessions."""

    cache_path = Path.home() / ".config" / "vibeplaylist" / "token.json"
    save_json(cache_path, {"token": token})
