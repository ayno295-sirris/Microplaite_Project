"""Application configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
APP_NAME = "microplaite_control"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_DIR = BASE_DIR / "logs"

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
DEFAULT_WINDOWS_PORT = "COM10"
DEFAULT_PI_PORT = "/dev/serial0"
DEFAULT_BAUDRATE = 115200
SERIAL_PORT_ENV = "MICROPLAITE_SERIAL_PORT"
ESP32_USB_HINTS = (
    "esp32",
    "espressif",
    "silicon labs",
    "cp210",
    "ch340",
    "usb serial",
    "usb-uart",
    "uart bridge",
)
LINUX_USB_SERIAL_GLOBS = (
    "/dev/serial/by-id/*",
    "/dev/ttyACM*",
    "/dev/ttyUSB*",
)
DEFAULT_TARGET_C = 37.50
DEFAULT_PID_KP = 8.0
DEFAULT_PID_KI = 0.03
DEFAULT_PID_KD = 20.0
DEFAULT_PID_LIMIT = 15.0
DEFAULT_LOG_PERIOD_MS = 200


def default_serial_port() -> str:
    configured_port = os.getenv(SERIAL_PORT_ENV)
    if configured_port:
        return configured_port
    if platform.system().lower().startswith("win"):
        return DEFAULT_WINDOWS_PORT
    return detect_esp32_serial_port() or DEFAULT_PI_PORT


def detect_esp32_serial_port() -> str | None:
    """Return the best ESP32 USB serial port detected on Linux."""

    pyserial_port = _detect_esp32_with_pyserial()
    if pyserial_port:
        return pyserial_port
    for pattern in LINUX_USB_SERIAL_GLOBS:
        matches = sorted(Path("/").glob(pattern.lstrip("/")))
        if matches:
            return str(matches[0])
    return None


def _detect_esp32_with_pyserial() -> str | None:
    try:
        from serial.tools import list_ports
    except Exception:
        return None

    ports = list(list_ports.comports(include_links=True))
    if not ports:
        return None
    return _choose_esp32_port(ports)


def _choose_esp32_port(ports: list[Any]) -> str | None:
    scored_ports = [
        (_serial_port_score(port), str(getattr(port, "device", "")))
        for port in ports
        if str(getattr(port, "device", ""))
    ]
    scored_ports = [item for item in scored_ports if item[0] > 0]
    if not scored_ports:
        return None
    scored_ports.sort(key=lambda item: (-item[0], item[1]))
    return scored_ports[0][1]


def _serial_port_score(port: Any) -> int:
    device = str(getattr(port, "device", ""))
    if not device.startswith(("/dev/ttyUSB", "/dev/ttyACM", "/dev/serial/by-id/")):
        return 0

    details = " ".join(
        str(getattr(port, name, "") or "")
        for name in (
            "device",
            "name",
            "description",
            "hwid",
            "manufacturer",
            "product",
            "interface",
        )
    ).lower()
    score = 10
    if device.startswith("/dev/serial/by-id/"):
        score += 30
    if getattr(port, "vid", None) is not None or getattr(port, "pid", None) is not None:
        score += 20
    if any(hint in details for hint in ESP32_USB_HINTS):
        score += 50
    return score


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
