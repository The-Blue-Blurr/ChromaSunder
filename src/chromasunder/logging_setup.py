"""Local rotating logs with no image-data or network output."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def log_path() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "chromasunder" / "chromasunder.log"


def configure_logging() -> Path:
    destination = log_path()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            destination,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        if not any(isinstance(item, RotatingFileHandler) for item in root.handlers):
            root.addHandler(handler)
        else:
            handler.close()
    except OSError:
        logging.getLogger(__name__).warning("Unable to create the ChromaSunder log file")
    return destination
