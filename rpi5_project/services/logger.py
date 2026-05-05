"""Logging setup for the Raspberry Pi supervisor."""

from __future__ import annotations

import logging

from app.config import AppConfig


LOG_FILE_NAME = "microplaite.log"


def setup_logging(config: AppConfig) -> None:
    """Configure console and file logging."""

    config.log_dir.mkdir(parents=True, exist_ok=True)
    log_file = config.log_dir / LOG_FILE_NAME

    level = getattr(logging, config.log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
