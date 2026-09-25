"""CSV logging for ESP32 V2 status snapshots."""

from __future__ import annotations

import csv
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TextIO

from microplaite_ui.core.state import AppState

DEFAULT_LOG_DIRECTORY = Path.home() / "MicroplaiteData" / "logs"
CSV_COLUMNS = (
    "timestamp_iso",
    "rpi_monotonic_ms",
    "esp32_uptime_ms",
    "temp_c",
    "temperature_valid",
    "temperature_fault",
    "heater_target_c",
    "heater_mode",
    "heater_output_percent",
    "heater_gpio_on",
    "safety",
    "last_error",
    "error_latched",
    "pump_running",
    "pump_rpm",
    "pump_full_speed",
    "pump_readback_valid",
    "system_state",
    "comm_state",
    "session_active",
    "heartbeat_age_ms",
    "neopixel_enabled",
    "neopixel_brightness",
)


class StatusCsvLogger:
    """Own one CSV file and append one row per received V2 STATUS."""

    def __init__(
        self,
        log_dir: Path | None = None,
        *,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.log_dir = log_dir or DEFAULT_LOG_DIRECTORY
        self._now = now or (lambda: datetime.now().astimezone())
        self._monotonic = monotonic or time.monotonic
        self._file: TextIO | None = None
        self._writer: csv.DictWriter | None = None
        self.path: Path | None = None

    @property
    def active(self) -> bool:
        return self._file is not None

    def start(self) -> Path:
        if self.active:
            assert self.path is not None
            return self.path

        self.log_dir.mkdir(parents=True, exist_ok=True)
        stamp = self._now().strftime("%Y-%m-%d_%H%M%S")
        path = self._unique_path(f"microplaite_{stamp}")
        csv_file = path.open("x", newline="", encoding="utf-8", buffering=1)
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        csv_file.flush()
        self.path = path
        self._file = csv_file
        self._writer = writer
        return path

    def write_status(self, state: AppState) -> None:
        if self._writer is None or self._file is None:
            return
        self._writer.writerow(
            {
                "timestamp_iso": self._now().isoformat(timespec="seconds"),
                "rpi_monotonic_ms": int(self._monotonic() * 1000),
                "esp32_uptime_ms": state.uptime_ms,
                "temp_c": state.temp_c,
                "temperature_valid": state.temperature_valid,
                "temperature_fault": state.temperature_fault,
                "heater_target_c": state.heater_target_c,
                "heater_mode": state.heater_mode,
                "heater_output_percent": state.heater_output_percent,
                "heater_gpio_on": state.heater_gpio_on,
                "safety": state.safety,
                "last_error": state.last_error,
                "error_latched": state.error_latched,
                "pump_running": state.pump_running,
                "pump_rpm": state.pump_rpm,
                "pump_full_speed": state.pump_full_speed,
                "pump_readback_valid": state.pump_readback_valid,
                "system_state": state.system_state,
                "comm_state": state.comm_state,
                "session_active": state.session_active,
                "heartbeat_age_ms": state.heartbeat_age_ms,
                "neopixel_enabled": state.neopixel_enabled,
                "neopixel_brightness": state.neopixel_brightness,
            }
        )
        self._file.flush()

    def stop(self) -> None:
        csv_file = self._file
        self._file = None
        self._writer = None
        if csv_file is not None:
            csv_file.flush()
            csv_file.close()

    def _unique_path(self, stem: str) -> Path:
        path = self.log_dir / f"{stem}.csv"
        index = 2
        while path.exists():
            path = self.log_dir / f"{stem}_{index}.csv"
            index += 1
        return path
