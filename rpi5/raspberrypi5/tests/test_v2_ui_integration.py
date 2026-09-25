from __future__ import annotations

import threading
import time

import pytest
from PySide6.QtWidgets import QApplication

from microplaite_ui.core.controller import AppController
from microplaite_ui.esp32.client import Esp32ClientError
from microplaite_ui.esp32.v2_client import V2Response, V2Status
from microplaite_ui.esp32.v2_session import SessionState
from microplaite_ui.esp32.v2_ui_client import V2UiClient
from microplaite_ui.main import create_v2_ui_client
from microplaite_ui.ui.main_window import MainWindow


class RecordingV2Client:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.status_value = _status()
        self.status_started = threading.Event()
        self.release_status = threading.Event()
        self.block_status = False
        self.status_error: Exception | None = None

    def status(self) -> V2Status:
        self.calls.append(("status",))
        self.status_started.set()
        status = self.status_value
        if self.block_status:
            assert self.release_status.wait(1.0)
        if self.status_error is not None:
            raise self.status_error
        return status

    def clear_error(self) -> V2Response:
        return self._record("clear_error")

    def heater_set_target(self, value: float) -> V2Response:
        return self._record("heater_set_target", value)

    def heater_set_pid(self, kp: float, ki: float, kd: float) -> V2Response:
        return self._record("heater_set_pid", kp, ki, kd)

    def heater_set_pid_limit(self, value: float) -> V2Response:
        return self._record("heater_set_pid_limit", value)

    def heater_set_power_limit(self, value: float) -> V2Response:
        return self._record("heater_set_power_limit", value)

    def heater_enable(self, mode: str) -> V2Response:
        return self._record("heater_enable", mode)

    def heater_disable(self) -> V2Response:
        return self._record("heater_disable")

    def pump_start(self, rpm: float) -> V2Response:
        return self._record("pump_start", rpm)

    def pump_stop(self) -> V2Response:
        return self._record("pump_stop")

    def pump_set_rpm(self, rpm: float) -> V2Response:
        return self._record("pump_set_rpm", rpm)

    def pump_prime(self) -> V2Response:
        return self._record("pump_prime")

    def pump_status(self) -> V2Response:
        return self._record("pump_status", pump_readback_valid=True)

    def neopixel_set(self, enabled: bool, brightness: int) -> V2Response:
        return self._record("neopixel_set", enabled, brightness)

    def stop(self) -> V2Response:
        return self._record("stop")

    def _record(self, name: str, *args, **payload) -> V2Response:
        self.calls.append((name, *args))
        return V2Response(1, "OK", name.upper(), payload)


class RecordingSession:
    def __init__(self, client: RecordingV2Client) -> None:
        self.client = client
        self.state = SessionState.DISCONNECTED
        self.open_calls = 0
        self.stop_calls = 0

    def open(self) -> V2Status:
        self.open_calls += 1
        self.state = SessionState.READY
        return self.client.status_value

    def stop(self) -> None:
        self.stop_calls += 1
        self.state = SessionState.DISCONNECTED


class FailingSession(RecordingSession):
    def open(self) -> V2Status:
        self.state = SessionState.LOST
        raise RuntimeError("USB unavailable")


def _status(**changes) -> V2Status:
    values = {
        "uptime_ms": 1000,
        "temp_c": 24.5,
        "temperature_valid": True,
        "temperature_fault": 0,
        "heater_mode": "PID",
        "heater_target_c": 44.0,
        "heater_output_percent": 12.5,
        "heater_gpio_on": True,
        "safety": "OK",
        "last_error": "NONE",
        "error_latched": False,
        "pump_running": True,
        "pump_rpm": 3.0,
        "pump_full_speed": False,
        "pump_readback_valid": True,
        "neopixel_enabled": True,
        "neopixel_brightness": 35,
        "system_state": "RUNNING",
        "comm_state": "ACTIVE",
        "session_active": True,
        "heartbeat_age_ms": 125,
    }
    values.update(changes)
    return V2Status(**values)


def _ready_controller() -> tuple[AppController, RecordingV2Client, RecordingSession]:
    client = RecordingV2Client()
    session = RecordingSession(client)
    controller = AppController(V2UiClient(session))
    controller.open_connection()
    return controller, client, session


def test_v2_status_maps_all_ui_state_fields() -> None:
    controller, _, session = _ready_controller()

    state = controller.state

    assert session.state is SessionState.READY
    assert state.connected is True
    assert state.temp_c == 24.5
    assert state.temperature_valid is True
    assert state.temperature_fault == 0
    assert state.heater_mode == "PID"
    assert state.heater_target_c == 44.0
    assert state.heater_output_percent == 12.5
    assert state.heater_gpio_on is True
    assert state.safety == "OK"
    assert state.last_error == ""
    assert state.error_latched is False
    assert state.pump_running is True
    assert state.pump_rpm == 3.0
    assert state.pump_full_speed is False
    assert state.pump_readback_valid is True
    assert state.neopixel_enabled is True
    assert state.neopixel_brightness == 35
    assert state.system_state == "RUNNING"
    assert state.comm_state == "ACTIVE"
    assert state.session_state == "READY"
    assert state.session_active is True
    assert state.heartbeat_age_ms == 125


def test_v2_controller_routes_heating_pump_neopixel_and_global_stop() -> None:
    controller, client, _ = _ready_controller()
    client.calls.clear()
    controller.state.target_c = 44.0
    controller.state.pump.target_rpm = 3.0

    controller.start_pid()
    controller.start_pump()
    controller.set_neopixel_brightness(35)
    controller.set_neopixel_enabled(True)
    controller.stop()

    assert client.calls == [
        ("clear_error",),
        ("heater_set_target", 44.0),
        ("heater_set_pid", 8.0, 0.03, 20.0),
        ("heater_set_pid_limit", 15.0),
        ("heater_enable", "PID"),
        ("status",),
        ("pump_start", 3.0),
        ("pump_status",),
        ("neopixel_set", True, 35),
        ("neopixel_set", True, 35),
        ("stop",),
    ]


def test_ui_stop_uses_hardware_stop_not_session_stop() -> None:
    controller, client, session = _ready_controller()
    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller)
    window.timer.stop()
    client.calls.clear()

    window.stop_button.click()
    app.processEvents()

    assert ("stop",) in client.calls
    assert session.stop_calls == 0


def test_v2_status_poll_never_starts_a_second_request_while_one_is_running() -> None:
    controller, client, _ = _ready_controller()
    client.calls.clear()
    client.block_status = True

    controller.poll_serial()
    assert client.status_started.wait(0.2)
    controller.poll_serial()
    controller.poll_serial()

    assert client.calls == [("status",)]
    client.release_status.set()
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline and controller.state.temp_c != 24.5:
        controller.poll_serial()
        time.sleep(0.005)


@pytest.mark.parametrize(
    ("session_state", "system_state"),
    [(SessionState.LOST, "IDLE"), (SessionState.READY, "FAULT")],
)
def test_lost_or_fault_disables_activation_but_keeps_stop_available(
    session_state: SessionState,
    system_state: str,
) -> None:
    controller, client, session = _ready_controller()
    session.state = session_state
    controller.state.session_state = session_state.value
    controller.state.system_state = system_state
    controller.state.comm_state = "LOST" if session_state is SessionState.LOST else "ACTIVE"
    controller.state.connected = session_state is SessionState.READY
    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller)
    window.timer.stop()
    window._render()
    client.calls.clear()

    assert window.start_button.isEnabled() is False
    assert window.temperature_start_button.isEnabled() is False
    assert window.pump_start_button.isEnabled() is False
    assert window.pump_prime_button.isEnabled() is False
    assert window.home_target_minus_button.isEnabled() is False
    assert window.home_target_plus_button.isEnabled() is False
    assert window.thermal_target_minus_button.isEnabled() is False
    assert window.thermal_target_plus_button.isEnabled() is False
    assert window.test_neopixel_on_button.isEnabled() is False
    assert window.test_neopixel_off_button.isEnabled() is True
    assert window.stop_button.isEnabled() is True
    window.stop_button.click()
    app.processEvents()

    assert client.calls[-1] == ("stop",)
    assert not any(call[0] in {"heater_enable", "pump_start", "pump_prime"} for call in client.calls)


def test_unconfirmed_pump_is_not_rendered_as_confirmed_stopped() -> None:
    controller, _, _ = _ready_controller()
    controller.state.pump_running = False
    controller.state.pump_readback_valid = False
    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller)
    window.timer.stop()
    window._render()
    app.processEvents()

    assert window.home_pump_status.text() == "Unconfirmed"
    assert window.pump_status.text() == "Unconfirmed"


def test_close_stops_session_without_sending_hardware_stop() -> None:
    controller, client, session = _ready_controller()
    client.calls.clear()

    controller.shutdown()

    assert session.stop_calls == 1
    assert ("stop",) not in client.calls


def test_lost_session_stops_status_polling_and_reports_connection_loss() -> None:
    controller, client, session = _ready_controller()
    client.calls.clear()
    session.state = SessionState.LOST

    controller.poll_serial()
    controller.poll_serial()

    assert client.calls == []
    assert controller.state.connected is False
    assert controller.state.session_state == "LOST"
    assert controller.state.comm_state == "LOST"
    assert controller.state.last_error == "ESP32 not connected"
    assert list(controller.logs).count("V2 session LOST") == 1


def test_failed_status_poll_does_not_queue_another_status() -> None:
    controller, client, _ = _ready_controller()
    client.calls.clear()
    client.status_error = RuntimeError("status failed")

    controller.poll_serial()
    assert client.status_started.wait(0.2)
    deadline = time.monotonic() + 0.5
    while controller.state.connected and time.monotonic() < deadline:
        controller.poll_serial()
        time.sleep(0.005)

    assert controller.state.connected is False
    assert client.calls == [("status",)]


def test_v2_adapter_translates_session_errors_to_controller_errors() -> None:
    controller, _, session = _ready_controller()
    session.state = SessionState.LOST

    with pytest.raises(Esp32ClientError):
        controller.client.read_available()


def test_production_factory_owns_one_v2_serial_transport() -> None:
    ui_client = create_v2_ui_client("/dev/test-esp32", baudrate=57600)

    assert isinstance(ui_client, V2UiClient)
    assert ui_client.client.transport.port == "/dev/test-esp32"
    assert ui_client.client.transport.baudrate == 57600
    assert ui_client.session.client is ui_client.client


def test_connection_failure_still_allows_ui_to_open_disconnected() -> None:
    client = RecordingV2Client()
    controller = AppController(V2UiClient(FailingSession(client)))

    controller.open_connection()
    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller)
    window.timer.stop()
    app.processEvents()

    assert controller.state.connected is False
    assert controller.state.session_state == "LOST"
    assert window.start_button.isEnabled() is False
    assert window.stop_button.isEnabled() is True


def test_v2_status_adds_valid_temperature_to_existing_history() -> None:
    controller, client, _ = _ready_controller()
    controller.state.temp_history.clear()
    client.status_value = _status(uptime_ms=1250, temp_c=25.25, temperature_valid=True)

    controller.refresh_status()

    assert list(controller.state.temp_history) == [(1250, 25.25)]


def test_v2_status_does_not_add_invalid_temperature_to_history() -> None:
    controller, client, _ = _ready_controller()
    controller.state.temp_history.clear()
    client.status_value = _status(uptime_ms=1250, temp_c=25.25, temperature_valid=False)

    controller.refresh_status()

    assert list(controller.state.temp_history) == []


def test_v2_temperature_history_uses_local_time_when_uptime_is_missing() -> None:
    controller, client, _ = _ready_controller()
    controller.state.temp_history.clear()
    client.status_value = _status(uptime_ms=None, temp_c=25.25, temperature_valid=True)

    controller.refresh_status()

    [(time_ms, temp_c)] = controller.state.temp_history
    assert time_ms >= 0
    assert temp_c == 25.25


def test_temperature_graph_receives_multiple_v2_status_points() -> None:
    controller, client, _ = _ready_controller()
    controller.state.temp_history.clear()
    for uptime_ms, temp_c in ((1200, 25.0), (1400, 25.5), (1600, 26.0)):
        client.status_value = _status(uptime_ms=uptime_ms, temp_c=temp_c)
        controller.refresh_status()
    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller)
    window.timer.stop()
    window._render()
    app.processEvents()

    xs, ys = window._plot_curves[0].getData()

    assert list(xs) == pytest.approx([0.0, 0.2, 0.4])
    assert list(ys) == pytest.approx([25.0, 25.5, 26.0])


def test_stale_status_cannot_overwrite_newer_confirmed_pump_status() -> None:
    controller, client, _ = _ready_controller()
    adapter = controller.client
    client.calls.clear()
    client.status_started.clear()
    client.block_status = True
    client.status_value = _status(pump_running=False, pump_readback_valid=False)

    controller.poll_serial()
    assert client.status_started.wait(0.2)

    command = threading.Thread(target=controller.start_pump)
    command.start()
    time.sleep(0.02)
    client.release_status.set()
    command.join(1.0)
    assert not command.is_alive()
    assert controller.state.pump_readback_valid is True

    client.block_status = False
    client.status_value = _status(pump_running=True, pump_readback_valid=True)
    controller.poll_serial()

    assert adapter.session_state == "READY"
    assert controller.state.pump_readback_valid is True


def test_newer_unconfirmed_status_is_not_hidden_after_pump_confirmation() -> None:
    controller, client, _ = _ready_controller()
    controller.start_pump()
    assert controller.state.pump_readback_valid is True
    client.status_value = _status(pump_running=True, pump_readback_valid=False)

    controller.refresh_status()

    assert controller.state.pump_running is True
    assert controller.state.pump_readback_valid is False


def test_lost_does_not_reconnect_until_operator_requests_it() -> None:
    controller, _, session = _ready_controller()
    session.state = SessionState.LOST

    controller.poll_serial()
    controller.poll_serial()
    controller.poll_serial()

    assert session.open_calls == 1
    assert controller.state.session_state == "LOST"


def test_reconnect_button_reopens_session_without_resuming_outputs() -> None:
    controller, client, session = _ready_controller()
    session.state = SessionState.LOST
    controller.poll_serial()
    controller.state.mode = "PID"
    controller.state.pump_running = True
    controller.state.neopixel_enabled = True
    client.status_value = _status(
        heater_mode="IDLE",
        heater_output_percent=0.0,
        heater_gpio_on=False,
        pump_running=False,
        pump_rpm=0.1,
        pump_readback_valid=True,
        neopixel_enabled=False,
        system_state="READY",
        comm_state="ACTIVE",
    )
    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller)
    window.timer.stop()
    window._render()
    client.calls.clear()

    assert window.reconnect_button.isEnabled() is True
    window.reconnect_button.click()
    app.processEvents()

    assert session.stop_calls == 1
    assert session.open_calls == 2
    assert controller.state.connected is True
    assert controller.state.session_state == "READY"
    assert controller.state.mode == "IDLE"
    assert controller.state.pump_running is False
    assert controller.state.neopixel_enabled is False
    assert not any(
        call[0] in {"heater_enable", "pump_start", "pump_prime", "neopixel_set"}
        for call in client.calls
    )
    assert window.reconnect_button.isEnabled() is False


def test_stop_is_operational_again_after_manual_reconnect() -> None:
    controller, client, session = _ready_controller()
    session.state = SessionState.LOST
    controller.poll_serial()
    client.status_value = _status(system_state="READY", comm_state="ACTIVE")

    controller.reconnect()
    client.calls.clear()
    controller.stop()

    assert client.calls == [("stop",)]
