"""Minimal Raspberry Pi application configuration."""

from dataclasses import dataclass
from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parents[1]
APP_NAME = "microplaite_control"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIR = BASE_DIR / "logs"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Configuration used by the Raspberry Pi supervisor skeleton."""

    app_name: str
    log_level: str
    log_dir: Path


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def load_config() -> AppConfig:
    """Load configuration from environment variables."""

    return AppConfig(
        app_name=_env("APP_NAME", APP_NAME),
        log_level=_env("LOG_LEVEL", DEFAULT_LOG_LEVEL),
        log_dir=Path(_env("LOG_DIR", str(DEFAULT_LOG_DIR))),
    )
