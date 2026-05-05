"""Entry point for the Raspberry Pi supervisor skeleton."""

from __future__ import annotations

import logging

from config import load_config
from logger import setup_logging


def main() -> None:
    config = load_config()
    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("Starting %s", config.app_name)
    logger.info("Log directory: %s", config.log_dir)
    logger.info("Raspberry Pi supervisor skeleton is ready")


if __name__ == "__main__":
    main()
