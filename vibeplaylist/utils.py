import logging
import os
from pathlib import Path


LOG_PATH = Path("app.log")


def configure_logging():
    LOG_PATH.touch(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler()
        ],
    )


def get_logger(name: str) -> logging.Logger:
    if not logging.getLogger().handlers:
        configure_logging()
    return logging.getLogger(name)


def ensure_config_dir() -> Path:
    config_dir = Path(os.path.expanduser("~/.config/vibeplaylist"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
