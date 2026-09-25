from __future__ import annotations

import csv
import os
from datetime import UTC, datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from microplaite_ui.core.controller import AppController
from microplaite_ui.core.state import AppState
from microplaite_ui.esp32.parser import ParsedMessage

EXPECTED_COLUMNS = [
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
]


def _logger(tmp_path):
    from microplaite_ui.services.status_csv_logger import StatusCsvLogger

    return StatusCsvLogger(
        tmp_path,
        now=lambda: datetime(2026, 9, 25, 18, 30, 45, tzinfo=UTC),
        monotonic=lambda: 123.456,
    )


class StatusStreamClient:
    port = "TEST"
    requires_active_session = True
    supports_legacy_logging = False

    def __init__(self) -> None:
        self.session_state = "READY"
        self.available: list[ParsedMessage] = []
        self.closed = False

    def read_available(self) -> list[ParsedMessage]:
        messages = self.available
        self.available = []
        return messages

    def close(self) -> None:
        self.closed = True


def test_start_creates_named_csv_with_expected_header(tmp_path) -> None:
    logger = _logger(tmp_path)

    path = logger.start()
    logger.stop()

    assert path.name == "microplaite_2026-09-25_183045.csv"
    with path.open(newline="", encoding="utf-8") as csv_file:
        assert next(csv.reader(csv_file)) == EXPECTED_COLUMNS


def test_write_status_records_multiple_snapshots_and_blank_none_values(tmp_path) -> None:
    logger = _logger(tmp_path)
    state = AppState()
    state.uptime_ms = 5000
    state.temp_c = 24.75
    state.temperature_valid = True
    state.temperature_fault = 0
    state.heater_target_c = 37.5
    state.heater_mode = "PID"
    state.heater_output_percent = 12.5
    state.heater_gpio_on = True
    state.safety = "OK"
    state.last_error = ""
    state.error_latched = False
    state.pump_running = True
    state.pump_rpm = 3.0
    state.pump_full_speed = False
    state.pump_readback_valid = True
    state.system_state = "RUNNING"
    state.comm_state = "ACTIVE"
    state.session_active = True
    state.heartbeat_age_ms = 120
    state.neopixel_enabled = True
    state.neopixel_brightness = 35

    path = logger.start()
    logger.write_status(state)
    state.temp_c = None
    state.temperature_valid = None
    state.heartbeat_age_ms = None
    logger.write_status(state)
    logger.stop()

    with path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert len(rows) == 2
    assert rows[0] == {
        "timestamp_iso": "2026-09-25T18:30:45+00:00",
        "rpi_monotonic_ms": "123456",
        "esp32_uptime_ms": "5000",
        "temp_c": "24.75",
        "temperature_valid": "True",
        "temperature_fault": "0",
        "heater_target_c": "37.5",
        "heater_mode": "PID",
        "heater_output_percent": "12.5",
        "heater_gpio_on": "True",
        "safety": "OK",
        "last_error": "",
        "error_latched": "False",
        "pump_running": "True",
        "pump_rpm": "3.0",
        "pump_full_speed": "False",
        "pump_readback_valid": "True",
        "system_state": "RUNNING",
        "comm_state": "ACTIVE",
        "session_active": "True",
        "heartbeat_age_ms": "120",
        "neopixel_enabled": "True",
        "neopixel_brightness": "35",
    }
    assert rows[1]["temp_c"] == ""
    assert rows[1]["temperature_valid"] == ""
    assert rows[1]["heartbeat_age_ms"] == ""
    assert "nan" not in path.read_text(encoding="utf-8").lower()


def test_start_is_idempotent_and_stop_is_safe(tmp_path) -> None:
    logger = _logger(tmp_path)

    first_path = logger.start()
    second_path = logger.start()
    logger.stop()
    logger.stop()

    assert first_path == second_path
    assert list(tmp_path.glob("*.csv")) == [first_path]
    assert logger.active is False
    assert logger.path == first_path


def test_controller_logs_each_v2_status_without_a_second_poll_loop(tmp_path) -> None:
    logger = _logger(tmp_path)
    client = StatusStreamClient()
    controller = AppController(client, status_logger=logger)
    controller.state.connected = True
    client.available = [
        ParsedMessage(
            ok=True,
            is_status=True,
            raw="V2 STATUS",
            fields={"uptime_ms": 1000, "temp_c": 24.5, "temperature_valid": True},
        ),
        ParsedMessage(ok=True, raw="V2 PING"),
        ParsedMessage(
            ok=True,
            is_status=True,
            raw="V2 STATUS",
            fields={"uptime_ms": 1200, "temp_c": 24.6, "temperature_valid": True},
        ),
    ]

    path = controller.start_logging()
    controller.poll_serial()
    controller.stop_logging()

    with path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert [row["esp32_uptime_ms"] for row in rows] == ["1000", "1200"]
    assert [row["temp_c"] for row in rows] == ["24.5", "24.6"]


def test_lost_session_flushes_and_stops_active_logging(tmp_path) -> None:
    logger = _logger(tmp_path)
    client = StatusStreamClient()
    controller = AppController(client, status_logger=logger)
    controller.state.connected = True
    client.available = [
        ParsedMessage(
            ok=True,
            is_status=True,
            raw="V2 STATUS",
            fields={"uptime_ms": 1000, "temp_c": 24.5, "temperature_valid": True},
        )
    ]

    path = controller.start_logging()
    controller.poll_serial()
    client.session_state = "LOST"
    controller.poll_serial()

    assert controller.logging_active is False
    with path.open(newline="", encoding="utf-8") as csv_file:
        assert len(list(csv.DictReader(csv_file))) == 1


def test_shutdown_closes_active_logger_before_client(tmp_path) -> None:
    logger = _logger(tmp_path)
    client = StatusStreamClient()
    controller = AppController(client, status_logger=logger)
    controller.state.connected = True
    controller.start_logging()

    controller.shutdown()

    assert controller.logging_active is False
    assert client.closed is True


def test_logs_button_controls_csv_logging_and_displays_active_file(tmp_path) -> None:
    # PySide6 must be selected before pyqtgraph is imported by MainWindow.
    from PySide6.QtWidgets import QApplication

    from microplaite_ui.ui.main_window import MainWindow

    logger = _logger(tmp_path)
    controller = AppController(StatusStreamClient(), status_logger=logger)
    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller)
    window.timer.stop()

    assert window.logs_button.text() == "START LOGGING"
    assert "Logging OFF" in window.bottom_status.text()

    window.logs_button.click()
    app.processEvents()

    assert controller.logging_active is True
    assert window.logs_button.text() == "STOP LOGGING"
    assert "Logging ON" in window.bottom_status.text()
    assert "microplaite_2026-09-25_183045.csv" in window.bottom_status.text()

    window.logs_button.click()
    app.processEvents()

    assert controller.logging_active is False
    assert window.logs_button.text() == "START LOGGING"
    assert "Logging OFF" in window.bottom_status.text()
