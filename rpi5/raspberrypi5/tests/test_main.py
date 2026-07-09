import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QLabel, QFrame, QPushButton

from microplaite_ui.config import DEFAULT_TARGET_C, SCREEN_HEIGHT, SCREEN_WIDTH
from microplaite_ui.core.controller import AppController
from microplaite_ui.core.state import AppState, TEMP_HISTORY_MAXLEN, derive_system_status
from microplaite_ui.esp32.fake_client import FakeEsp32Client
from microplaite_ui.esp32.parser import ParsedMessage, parse_line
from microplaite_ui.services import timelapse as timelapse_module
from microplaite_ui.ui.main_window import MainWindow


class RecordingClient:
    port = "TEST"

    def __init__(self) -> None:
        self.commands: list[str] = []
        self.available: list[ParsedMessage] = []
        self.mode = "IDLE"

    def status(self) -> ParsedMessage:
        self.commands.append("STATUS")
        return ParsedMessage(ok=True, raw="OK STATUS", fields={"mode": self.mode, "last_error": "NONE"})

    def read_temp(self) -> ParsedMessage:
        self.commands.append("READ_TEMP")
        return ParsedMessage(ok=True)

    def clear_error(self) -> ParsedMessage:
        self.commands.append("CLEAR_ERROR")
        return ParsedMessage(ok=True, fields={"last_error": ""})

    def set_target(self, temp_c: float) -> ParsedMessage:
        self.commands.append(f"SET_TARGET {temp_c:.2f}")
        return ParsedMessage(ok=True, fields={"target_c": temp_c})

    def set_pid(self, kp: float, ki: float, kd: float) -> ParsedMessage:
        self.commands.append(f"SET_PID {kp:g} {ki:g} {kd:g}")
        return ParsedMessage(ok=True)

    def set_pid_limit(self, percent: float) -> ParsedMessage:
        self.commands.append(f"SET_PID_LIMIT {percent:g}")
        return ParsedMessage(ok=True)

    def pid_on(self) -> ParsedMessage:
        self.commands.append("PID_ON")
        self.mode = "PID"
        return ParsedMessage(ok=True, fields={"mode": "PID"})

    def pid_off(self) -> ParsedMessage:
        self.commands.append("PID_OFF")
        self.mode = "IDLE"
        return ParsedMessage(ok=True, fields={"mode": "IDLE"})

    def stop(self) -> ParsedMessage:
        self.commands.append("STOP")
        self.mode = "IDLE"
        return ParsedMessage(
            ok=True,
            fields={
                "mode": "IDLE",
                "heater_output_percent": 0.0,
                "pump_running": False,
                "pump_rpm": 0.0,
                "pump_full_speed": False,
            },
        )

    def pump_start(self, rpm: float) -> ParsedMessage:
        self.commands.append(f"PUMP_START {rpm:.1f}")
        return ParsedMessage(
            ok=True,
            fields={"pump_running": True, "pump_rpm": rpm, "pump_full_speed": False},
        )

    def pump_stop(self) -> ParsedMessage:
        self.commands.append("PUMP_STOP")
        return ParsedMessage(
            ok=True,
            fields={"pump_running": False, "pump_rpm": 0.0, "pump_full_speed": False},
        )

    def pump_set_rpm(self, rpm: float) -> ParsedMessage:
        self.commands.append(f"PUMP_SET_RPM {rpm:.1f}")
        return ParsedMessage(ok=True, fields={"pump_running": True, "pump_rpm": rpm})

    def pump_prime(self) -> ParsedMessage:
        self.commands.append("PUMP_PRIME")
        return ParsedMessage(
            ok=True,
            fields={"pump_running": True, "pump_rpm": 100.0, "pump_full_speed": True},
        )

    def pump_status(self) -> ParsedMessage:
        self.commands.append("PUMP_STATUS")
        return ParsedMessage(ok=True, fields={"pump_readback": True})

    def neopixel_on(self) -> ParsedMessage:
        self.commands.append("NEOPIXEL_ON")
        return ParsedMessage(ok=True, fields={"neopixel_enabled": True})

    def neopixel_off(self) -> ParsedMessage:
        self.commands.append("NEOPIXEL_OFF")
        return ParsedMessage(ok=True, fields={"neopixel_enabled": False})

    def neopixel_brightness(self, percent: int) -> ParsedMessage:
        self.commands.append(f"NEOPIXEL_BRIGHTNESS {percent}")
        return ParsedMessage(ok=True, fields={"neopixel_brightness_percent": percent})

    def log_on(self, period_ms: int) -> ParsedMessage:
        self.commands.append(f"LOG_ON {period_ms}")
        return ParsedMessage(ok=True)

    def log_off(self) -> ParsedMessage:
        self.commands.append("LOG_OFF")
        return ParsedMessage(ok=True)

    def read_available(self) -> list[ParsedMessage]:
        messages = self.available
        self.available = []
        return messages

    def close(self) -> None:
        self.commands.append("CLOSE")


def test_controller_starts_pid_with_fake_client() -> None:
    controller = AppController(FakeEsp32Client())

    controller.start_pid()

    assert controller.state.connected is True
    assert controller.state.mode == "PID"
    assert controller.state.target_c == DEFAULT_TARGET_C


def test_controller_stop_is_always_available() -> None:
    controller = AppController(FakeEsp32Client())
    controller.start_pid()

    controller.stop()

    assert controller.state.mode == "IDLE"
    assert controller.state.heater_output_percent == 0.0


def test_controller_updates_state_from_log_line() -> None:
    client = RecordingClient()
    controller = AppController(client)
    controller.state.connected = True
    client.available.append(parse_line("LOG TEMP 25.10C SENSOR_VALID 1 FAULT 0 MODE PID HEATER_OUTPUT 9.0%"))

    controller.poll_serial()

    assert controller.state.temp_c == 25.10
    assert controller.state.sensor_valid is True
    assert controller.state.fault is False
    assert controller.state.mode == "PID"
    assert controller.state.heater_output_percent == 9.0


def test_controller_updates_state_from_csv_log_line() -> None:
    client = RecordingClient()
    controller = AppController(client)
    controller.state.connected = True
    client.available.append(parse_line("LOG,799678,34.70,37.50,15.0,ON,PID,1,0"))

    controller.poll_serial()

    assert controller.state.time_ms == 799678
    assert controller.state.temp_c == 34.70
    assert controller.state.target_c == 37.50
    assert controller.state.heater_output_percent == 15.0
    assert controller.state.gpio14 == "ON"
    assert controller.state.mode == "PID"
    assert controller.state.sensor_valid is True
    assert controller.state.fault is False


def test_derive_system_status_values() -> None:
    disconnected = AppState(connected=False)
    idle = AppState(connected=True)
    running = AppState(connected=True)
    running.mode = "PID"
    heater_running = AppState(connected=True)
    heater_running.heater_output_percent = 1.0
    error = AppState(connected=True)
    error.last_error = "SENSOR"

    assert derive_system_status(disconnected) == "DISCONNECTED"
    assert derive_system_status(idle) == "IDLE"
    assert derive_system_status(running) == "RUNNING"
    assert derive_system_status(heater_running) == "RUNNING"
    assert derive_system_status(error) == "ERROR"


def test_neopixel_controls_send_esp32_commands() -> None:
    client = RecordingClient()
    controller = AppController(client)

    controller.set_neopixel_enabled(True)
    controller.set_neopixel_brightness(80)
    controller.set_neopixel_enabled(False)

    assert controller.state.neopixel.enabled is False
    assert controller.state.neopixel.brightness_percent == 80
    assert client.commands == ["NEOPIXEL_ON", "NEOPIXEL_BRIGHTNESS 80", "NEOPIXEL_OFF"]


def test_pump_controls_send_esp32_commands() -> None:
    client = RecordingClient()
    controller = AppController(client)

    controller.set_pump_target_rpm(80)
    controller.start_pump()
    controller.set_pump_target_rpm(60)
    controller.prime_pump()
    controller.stop_pump()

    assert controller.state.pump.running is False
    assert controller.state.pump.target_rpm == 60
    assert controller.state.pump.actual_rpm == 0
    assert client.commands == [
        "PUMP_START 80.0",
        "PUMP_STATUS",
        "PUMP_SET_RPM 60.0",
        "PUMP_STATUS",
        "PUMP_PRIME",
        "PUMP_STATUS",
        "PUMP_STOP",
        "PUMP_STATUS",
    ]


def test_pump_target_accepts_decimal_rpm() -> None:
    client = RecordingClient()
    controller = AppController(client)

    controller.set_pump_target_rpm(9.9)
    controller.start_pump()
    controller.set_pump_target_rpm(9.8)

    assert controller.state.pump.target_rpm == 9.8
    assert controller.state.pump.actual_rpm == 9.8
    assert client.commands == [
        "PUMP_START 9.9",
        "PUMP_STATUS",
        "PUMP_SET_RPM 9.8",
        "PUMP_STATUS",
    ]


def test_start_pump_updates_state_from_serial_response() -> None:
    client = RecordingClient()
    controller = AppController(client)

    controller.set_pump_target_rpm(80)
    controller.start_pump()

    assert controller.state.pump.running is True
    assert controller.state.pump.target_rpm == 80
    assert controller.state.pump.actual_rpm == 80
    assert controller.state.pump.readback is True
    assert client.commands == ["PUMP_START 80.0", "PUMP_STATUS"]


def test_stop_pump_sends_serial_command() -> None:
    client = RecordingClient()
    controller = AppController(client)
    controller.set_pump_target_rpm(70)
    controller.start_pump()

    controller.stop_pump()

    assert controller.state.pump.running is False
    assert controller.state.pump.actual_rpm == 0
    assert client.commands == ["PUMP_START 70.0", "PUMP_STATUS", "PUMP_STOP", "PUMP_STATUS"]


def test_start_pid_sends_expected_sequence() -> None:
    client = RecordingClient()
    controller = AppController(client)
    controller.state.target_c = 37.5

    controller.start_pid()

    assert client.commands == [
        "CLEAR_ERROR",
        "SET_TARGET 37.50",
        "SET_PID 8 0.03 20",
        "SET_PID_LIMIT 15",
        "PID_ON",
        "STATUS",
    ]


def test_stop_sends_stop_immediately() -> None:
    client = RecordingClient()
    controller = AppController(client)

    controller.stop()

    assert client.commands == ["STOP"]
    assert controller.state.pump.running is False


def test_state_history_receives_log_point_and_caps_to_1500() -> None:
    client = RecordingClient()
    controller = AppController(client)
    controller.state.connected = True

    for i in range(1600):
        client.available.append(parse_line(f"LOG,{i * 200},{30.0 + (i % 5):.2f},37.50,0.0,OFF,IDLE,1,0"))
        controller.poll_serial()

    assert len(controller.state.temp_history) == TEMP_HISTORY_MAXLEN
    assert controller.state.temp_history[-1][1] == 34.0


def test_layout_constants_fit_1280x720() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()
    window.show()
    app.processEvents()

    assert window.width() == SCREEN_WIDTH
    assert window.height() == SCREEN_HEIGHT
    assert window.log_view.height() <= 80
    assert window.stop_button.height() >= 50
    assert window.start_button.isVisible()
    assert window.start_button.width() == 200
    assert window.start_button.sizeHint().width() <= window.start_button.width()
    window.start_button.setText("STOP PID")
    assert window.start_button.sizeHint().width() <= window.start_button.width()
    window.start_button.setText("START")
    window.home_temp_value.setText("88.88 °C")
    assert window.home_temp_value.sizeHint().width() <= window.home_temp_value.width()
    assert window.home_setpoint.sizeHint().width() <= window.home_setpoint.width()
    assert window.home_setpoint.sizeHint().height() <= window.home_setpoint.height()
    assert window.home_heater.sizeHint().height() <= window.home_heater.height()
    assert window.home_heater.x() == window.start_button.x()
    assert window.home_heater.y() > window.start_button.geometry().bottom()
    assert not hasattr(window, "home_system_status")
    temperature_cards = [card for card in window.home_page.findChildren(QFrame) if card.objectName() == "temperatureCard"]
    camera_cards = [card for card in window.home_page.findChildren(QFrame) if card.objectName() == "cameraCard"]
    assert camera_cards[0].width() >= 700
    assert camera_cards[0].height() >= 280
    window._camera_image = QImage(320, 240, QImage.Format.Format_RGB32)
    window._camera_image.fill(0x216EE5)
    window._paint_camera_image()
    assert window.home_camera_preview.pixmap().size() == window.home_camera_preview.size()
    assert not [card for card in window.home_page.findChildren(QFrame) if card.objectName() == "thermalCard"]
    assert window.stop_button.isVisible()
    assert window.clear_button.isVisible()
    assert window.refresh_button.isVisible()
    assert window.stop_button.y() > max(
        temperature_cards[0].geometry().bottom(),
        camera_cards[0].geometry().bottom(),
    )
    assert window.clear_button.y() == window.stop_button.y()
    assert window.refresh_button.y() == window.stop_button.y()
    assert window.log_view.geometry().bottom() <= window.home_page.height()

    window.setFixedSize(SCREEN_WIDTH, 640)
    app.processEvents()
    assert window.stop_button.y() > max(
        temperature_cards[0].geometry().bottom(),
        camera_cards[0].geometry().bottom(),
    )
    assert window.log_view.geometry().bottom() <= window.home_page.height()


def test_main_window_starts_status_then_log_on_when_connected() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    client = RecordingClient()

    window = MainWindow(AppController(client))
    window.timer.stop()

    assert client.commands[:2] == ["STATUS", "LOG_ON 200"]


def test_home_pid_button_starts_and_stops_pid() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    client = RecordingClient()
    window = MainWindow(AppController(client))
    window.timer.stop()
    client.commands.clear()

    window.start_button.click()

    assert window.start_button.text() == "STOP PID"
    assert client.commands == [
        "CLEAR_ERROR",
        "SET_TARGET 37.50",
        "SET_PID 8 0.03 20",
        "SET_PID_LIMIT 15",
        "PID_ON",
        "STATUS",
        "LOG_ON 200",
    ]

    client.commands.clear()
    window.start_button.click()

    assert window.start_button.text() == "START"
    assert client.commands == ["PID_OFF"]


def test_temperature_dashboard_has_pid_controls_and_no_footer_cards() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()
    window.show_temperature_page()
    window.show()
    app.processEvents()

    assert window.temperature_start_button.isVisible()
    assert window.temperature_target_minus_button.isVisible()
    assert window.temperature_target_plus_button.isVisible()
    assert window.temperature_target_minus_button.width() >= 56
    assert window.temperature_target_plus_button.height() >= 50
    target_card = window.temperature_target_minus_button.parentWidget()
    assert window.temperature_target_minus_button.geometry().bottom() <= target_card.height()
    assert window.temperature_target_plus_button.geometry().bottom() <= target_card.height()
    assert window.temperature_plot.height() >= 340
    assert not hasattr(window, "temperature_mode")
    assert not hasattr(window, "temperature_sensor")
    assert not hasattr(window, "temperature_fault")
    assert not hasattr(window, "temperature_error")
    page_text = "\n".join(label.text() for label in window.temperature_page.findChildren(QLabel))
    assert "Mode" not in page_text
    assert "Last error" not in page_text


def test_temperature_dashboard_controls_pid_and_setpoint() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    client = RecordingClient()
    window = MainWindow(AppController(client))
    window.timer.stop()
    window.show_temperature_page()
    client.commands.clear()

    window.temperature_target_plus_button.click()

    assert window.controller.state.target_c == 37.6
    assert window.temperature_target_value.text() == "37.60 °C"
    assert client.commands == ["SET_TARGET 37.60"]

    client.commands.clear()
    window.temperature_start_button.click()

    assert window.temperature_start_button.text() == "STOP PID"
    assert window.start_button.text() == "STOP PID"
    assert client.commands == [
        "CLEAR_ERROR",
        "SET_TARGET 37.60",
        "SET_PID 8 0.03 20",
        "SET_PID_LIMIT 15",
        "PID_ON",
        "STATUS",
        "LOG_ON 200",
    ]


def test_main_window_restores_user_preferences_between_sessions() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    first = MainWindow(AppController(FakeEsp32Client()))
    first.timer.stop()

    first._nudge_target(0.1)
    first._set_pump_target_rpm(9.8)
    first._set_neopixel_enabled(False)
    first._set_neopixel_brightness(35)
    first.storage_combo.setCurrentIndex(1)
    first.interval_spin.setValue(7)
    first.interval_unit.setCurrentIndex(1)
    first._set_timelapse_brightness_value(42, send_to_esp32=False)
    first.light_duration_spin.setValue(2.3)
    first.total_duration_spin.setValue(90)
    first.infinite_check.setChecked(True)
    first._save_preferences()

    second = MainWindow(AppController(FakeEsp32Client()))
    second.timer.stop()

    assert second.controller.state.target_c == 37.6
    assert second.controller.state.pump.target_rpm == 9.8
    assert second.controller.state.neopixel.enabled is False
    assert second.controller.state.neopixel.brightness_percent == 35
    assert second.storage_combo.currentData() == "external"
    assert second.interval_spin.value() == 7
    assert second.interval_unit.currentData() == 60
    assert second.timelapse_brightness_spin.value() == 42
    assert second.test_brightness_spin.value() == 42
    assert second.light_duration_spin.value() == 2.3
    assert second.total_duration_spin.value() == 90
    assert second.infinite_check.isChecked() is True


def test_navigation_methods_select_expected_pages() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()

    window.show_temperature_page()
    assert window.pages.currentIndex() == MainWindow.PAGE_TEMPERATURE
    window.show_thermal_page()
    assert window.pages.currentIndex() == MainWindow.PAGE_THERMAL
    window.show_pump_page()
    assert window.pages.currentIndex() == MainWindow.PAGE_PUMP
    window.show_timelapse_page()
    assert window.pages.currentIndex() == MainWindow.PAGE_TIMELAPSE
    window.show_camera_page()
    assert window.pages.currentIndex() == MainWindow.PAGE_CAMERA
    window.show_home_page()
    assert window.pages.currentIndex() == MainWindow.PAGE_HOME


def test_thermal_detail_layout_starts_high_and_fits_screen() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()
    window.show_thermal_page()
    window.show()
    app.processEvents()

    assert window.thermal_hero_card.y() <= 140
    assert window.thermal_hero_card.geometry().bottom() < SCREEN_HEIGHT
    assert window.thermal_error.parentWidget().geometry().bottom() <= SCREEN_HEIGHT
    assert window.pid_card.width() < 500
    assert window.pid_card.height() >= 260
    assert window.thermal_graph_card.width() >= 740
    assert window.thermal_graph_card.height() >= 260
    assert window.thermal_plot.height() >= 220
    page_text = "\n".join(label.text() for label in window.thermal_page.findChildren(QLabel))
    assert "Read-only tuning values" not in page_text


def test_status_pills_are_compact() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()
    window.show()
    app.processEvents()

    for pill in window._status_pills:
        assert pill.width() <= 180
        assert pill.height() <= 50


def test_timelapse_page_replaces_neopixel_card_and_shows_controls() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()
    window.show_timelapse_page()
    window.show()
    app.processEvents()

    assert window.pages.currentIndex() == MainWindow.PAGE_TIMELAPSE
    assert window.storage_combo.currentData() == "internal"
    assert window.timelapse_brightness_spin.value() == 80
    assert window.light_duration_spin.value() == 1.0
    assert window.home_timelapse_status.text() == "Stopped"
    assert "Path:" in window.timelapse_path.text()
    assert window.timelapse_stack.currentIndex() == 0
    texts = {button.text() for button in window.timelapse_page.findChildren(QPushButton)}
    assert {
        "ACQUISITION",
        "TEST PHOTO",
        "START TIMELAPSE",
        "STOP",
        "STOP TIMELAPSE",
        "TEST CAPTURE",
        "START LIVE",
        "STOP LIVE",
        "ON",
        "OFF",
    } <= texts

    window._show_timelapse_tab(1)

    assert window.timelapse_stack.currentIndex() == 1
    assert window.timelapse_test_tab.objectName() == "tabButtonActive"
    assert window.timelapse_acquisition_tab.objectName() == "tabButton"


def test_timelapse_fields_use_large_step_buttons() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()

    for button in (
        window.interval_minus_button,
        window.interval_plus_button,
        window.timelapse_brightness_minus_button,
        window.timelapse_brightness_plus_button,
        window.light_duration_minus_button,
        window.light_duration_plus_button,
        window.total_duration_minus_button,
        window.total_duration_plus_button,
        window.test_brightness_minus_button,
        window.test_brightness_plus_button,
    ):
        assert button.width() >= 56
        assert button.height() >= 44


def test_timelapse_step_buttons_update_numeric_fields() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()

    window.interval_plus_button.click()
    assert window.interval_spin.value() == 11
    window.interval_minus_button.click()
    assert window.interval_spin.value() == 10

    window.timelapse_brightness_plus_button.click()
    assert window.timelapse_brightness_spin.value() == 81
    assert window.test_brightness_spin.value() == 81

    window.light_duration_minus_button.click()
    assert window.light_duration_spin.value() == 0.9
    window.light_duration_plus_button.click()
    assert window.light_duration_spin.value() == 1.0

    window.total_duration_minus_button.click()
    assert window.total_duration_spin.value() == 59
    window.total_duration_plus_button.click()
    assert window.total_duration_spin.value() == 60

    window._show_timelapse_tab(1)
    window.test_brightness_minus_button.click()
    assert window.timelapse_brightness_spin.value() == 80
    assert window.test_brightness_spin.value() == 80


def test_timelapse_start_refuses_when_live_video_is_active() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()

    assert window.timelapse_service.set_live_running(True) is True
    window._camera_mode = "live"
    window._start_timelapse()

    snap = window.timelapse_service.snapshot()
    assert snap.running is False
    assert snap.live_running is True
    assert "Stop live video before starting timelapse" in window.timelapse_error.text()
    assert "Stop live video before starting timelapse" in window.controller.logs


def test_live_video_start_refuses_when_timelapse_is_active() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()

    window.timelapse_service._set_snapshot(running=True, status="timelapse running")
    window._camera_mode = "timelapse"
    window._start_live_video()

    snap = window.timelapse_service.snapshot()
    assert snap.running is True
    assert snap.live_running is False
    assert "Stop timelapse before starting live video" in window.timelapse_error.text()
    assert "Stop timelapse before starting live video" in window.controller.logs


def test_live_video_start_turns_neopixel_on_and_stop_turns_it_off(monkeypatch) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    client = RecordingClient()
    window = MainWindow(AppController(client))
    window.timer.stop()
    window.test_brightness_spin.setValue(66)
    client.commands.clear()

    def fake_start_usb_camera(mode: str) -> bool:
        window._camera_mode = mode
        image = QImage(32, 24, QImage.Format.Format_RGB32)
        image.fill(0x216EE5)
        with window._camera_image_lock:
            window._camera_image = image
        return True

    monkeypatch.setattr(window, "_start_usb_camera", fake_start_usb_camera)

    window._start_live_video()

    assert window.timelapse_service.snapshot().live_running is True
    assert window.controller.state.neopixel.enabled is True
    assert window.home_camera_badge.text() == "Live"
    assert window.timelapse_camera_badge.text() == "Live"
    assert window.camera_preview_badge.text() == "Live"
    assert client.commands == ["NEOPIXEL_BRIGHTNESS 66", "NEOPIXEL_ON"]

    client.commands.clear()
    window._stop_live_video()

    assert window.timelapse_service.snapshot().live_running is False
    assert window.controller.state.neopixel.enabled is False
    assert client.commands == ["NEOPIXEL_OFF"]


def test_test_capture_refuses_when_live_video_is_active() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()

    window._show_timelapse_tab(1)
    assert window.timelapse_service.set_live_running(True) is True
    window._camera_mode = "live"
    window._test_capture()

    assert window.timelapse_service.snapshot().last_file == ""
    assert "Stop live video before test capture" in window.timelapse_error.text()
    assert "Stop live video before test capture" in window.controller.logs


def test_test_capture_runs_without_live_and_toggles_neopixel(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(timelapse_module, "INTERNAL_STORAGE", tmp_path)
    app = QApplication.instance() or QApplication(sys.argv)
    client = RecordingClient()
    window = MainWindow(AppController(client))
    window.timer.stop()
    window._show_timelapse_tab(1)
    window.show()
    app.processEvents()
    client.commands.clear()

    def fake_start_usb_camera(mode: str) -> bool:
        window._camera_mode = mode
        image = QImage(32, 24, QImage.Format.Format_RGB32)
        image.fill(0x216EE5)
        with window._camera_image_lock:
            window._camera_image = image
        return True

    monkeypatch.setattr(window, "_start_usb_camera", fake_start_usb_camera)
    window.light_duration_spin.setValue(0.0)

    window._test_capture()

    saved = list(tmp_path.glob("test_capture_*.jpg"))
    assert len(saved) == 1
    assert window.timelapse_service.snapshot().last_file == str(saved[0])
    assert window._camera_mode == "idle"
    assert window.home_camera_badge.text() == "Last picture"
    assert window.timelapse_camera_badge.text() == "Last picture"
    assert window.camera_preview_badge.text() == "Last picture"
    assert window.home_camera_preview.pixmap() is not None
    assert window.timelapse_live_preview.pixmap() is not None
    assert window.camera_preview.pixmap() is not None
    assert client.commands == [
        "NEOPIXEL_BRIGHTNESS 80",
        "NEOPIXEL_ON",
        "NEOPIXEL_OFF",
    ]


def test_timelapse_camera_preview_uses_only_saved_images(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()

    last_picture = QImage(8, 8, QImage.Format.Format_RGB32)
    last_picture.fill(0xAA0000)
    live_frame = QImage(8, 8, QImage.Format.Format_RGB32)
    live_frame.fill(0x0022CC)
    with window._camera_image_lock:
        window._last_picture_image = last_picture
        window._camera_image = live_frame
    window._camera_mode = "timelapse"

    assert window._preview_badge_text() == "Last picture"
    assert window._preview_image().pixelColor(0, 0).name() == "#aa0000"

    saved = window._save_camera_image(tmp_path / "saved.jpg")

    assert saved == tmp_path / "saved.jpg"
    assert window._last_picture_path == str(saved)
    assert window._preview_badge_text() == "Last picture"
    assert window._preview_image().pixelColor(0, 0).name() == "#0022cc"


def test_timelapse_stop_button_stays_visible_on_both_tabs() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()
    window.show_timelapse_page()
    window.show()
    app.processEvents()

    for index in (0, 1):
        window._show_timelapse_tab(index)
        app.processEvents()
        assert window.stop_timelapse_button.text() == "STOP TIMELAPSE"
        assert window.stop_timelapse_button.isVisible()
        assert window.stop_timelapse_button.x() < 900


def test_timelapse_cards_and_bottom_buttons_fit_screen() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()
    window.show_timelapse_page()
    window.show()
    app.processEvents()

    assert window.timelapse_acquisition_card.geometry().bottom() <= window.timelapse_page.height()
    assert window.timelapse_status_card.geometry().bottom() <= window.timelapse_page.height()
    assert window.start_timelapse_button.geometry().bottom() <= window.start_timelapse_button.parentWidget().height()

    window._show_timelapse_tab(1)
    app.processEvents()

    assert window.test_photo_controls_card.geometry().bottom() <= window.timelapse_page.height()
    assert window.test_photo_preview_card.geometry().bottom() <= window.timelapse_page.height()
    assert window.test_capture_button.geometry().bottom() <= window.test_capture_button.parentWidget().height()
    assert window.start_live_button.sizeHint().width() <= window.start_live_button.width()
    assert window.stop_live_button.sizeHint().width() <= window.stop_live_button.width()


def test_pump_page_controls_update_local_state_and_home_card() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    client = RecordingClient()
    window = MainWindow(AppController(client))
    window.timer.stop()
    client.commands.clear()

    window.pump_slider.setValue(75)
    window._start_pump()

    assert window.controller.state.pump.running is True
    assert window.controller.state.pump.target_rpm == 75
    assert window.controller.state.pump.actual_rpm == 75
    assert window.pump_spin.value() == 75
    assert window.home_pump_status.text() == "Running"
    assert window.home_pump_rpm.text() == "75 RPM"
    assert client.commands == ["PUMP_START 75.0", "PUMP_STATUS"]


def test_pump_page_large_step_buttons_use_fine_steps_below_10_rpm() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()

    window._set_pump_target_rpm(9.8)
    window._nudge_pump_target(1)
    assert window.controller.state.pump.target_rpm == 9.9
    assert window.pump_spin.value() == 9.9
    assert window.pump_target_rpm.text() == "9.9 RPM"

    window._nudge_pump_target(1)
    assert window.controller.state.pump.target_rpm == 10.0
    assert window.pump_target_rpm.text() == "10 RPM"

    window._nudge_pump_target(1)
    assert window.controller.state.pump.target_rpm == 11.0
    assert window.pump_target_rpm.text() == "11 RPM"

    window._set_pump_target_rpm(10.0)
    window._nudge_pump_target(-1)
    assert window.controller.state.pump.target_rpm == 9.9


def test_pump_page_uses_large_step_buttons() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()

    assert window.pump_minus_button.text() == "-"
    assert window.pump_plus_button.text() == "+"
    assert window.pump_minus_button.width() >= 90
    assert window.pump_plus_button.height() >= 70


def test_camera_page_contains_live_controls_and_full_preview() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(AppController(FakeEsp32Client()))
    window.timer.stop()
    window.show_camera_page()
    window.show()
    app.processEvents()

    buttons = window.camera_page.findChildren(QPushButton)

    assert window.camera_back_button in buttons
    assert window.camera_start_live_button in buttons
    assert window.camera_stop_live_button in buttons
    assert window.camera_back_button.text() == "BACK"
    assert window.camera_start_live_button.text() == "START LIVE"
    assert window.camera_stop_live_button.text() == "STOP LIVE"
    assert window.camera_preview.objectName() == "cameraFullPreview"
    assert window.camera_preview.y() <= 90
    assert window.camera_preview.height() >= 590
    assert not hasattr(window, "camera_status")
