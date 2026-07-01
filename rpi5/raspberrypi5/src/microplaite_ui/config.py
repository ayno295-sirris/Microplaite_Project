"""Application configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform


BASE_DIR = Path(__file__).resolve().parents[2]
APP_NAME = "microplaite_control"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIR = BASE_DIR / "logs"

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
DEFAULT_WINDOWS_PORT = "COM10"
DEFAULT_PI_PORT = "/dev/serial0"
DEFAULT_BAUDRATE = 115200
DEFAULT_TARGET_C = 37.50
DEFAULT_PID_KP = 8.0
DEFAULT_PID_KI = 0.03
DEFAULT_PID_KD = 20.0
DEFAULT_PID_LIMIT = 15.0
DEFAULT_LOG_PERIOD_MS = 200


def default_serial_port() -> str:
    if platform.system().lower().startswith("win"):
        return DEFAULT_WINDOWS_PORT
    return DEFAULT_PI_PORT


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime configuration shared by scripts and logging."""

    app_name: str
    log_level: str
    log_dir: Path


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def load_config() -> AppConfig:
    return AppConfig(
        app_name=_env("APP_NAME", APP_NAME),
        log_level=_env("LOG_LEVEL", DEFAULT_LOG_LEVEL),
        log_dir=Path(_env("LOG_DIR", str(DEFAULT_LOG_DIR))),
    )
