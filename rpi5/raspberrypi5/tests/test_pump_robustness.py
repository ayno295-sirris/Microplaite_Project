"""Pump transactions against the real controller and V2 UI adapter, without hardware."""

from __future__ import annotations

import csv
import json
import threading
import time
from collections import deque

import pytest
from PySide6.QtWidgets import QApplication

from microplaite_ui.core.controller import AppController
from microplaite_ui.core.state import derive_system_status
from microplaite_ui.esp32.parser import ParsedMessage
from microplaite_ui.esp32.v2_client import V2Client, V2Esp32Error, V2Response, V2Status
from microplaite_ui.esp32.v2_session import SessionState, V2Session
from microplaite_ui.esp32.v2_ui_client import V2UiClient
from microplaite_ui.services.status_csv_logger import StatusCsvLogger
from microplaite_ui.ui.main_window import MainWindow


class PumpPeer:
    """WJ reports the command; only RJ reports the simulated pump readback."""

    def __init__(self) -> None:
        self.calls = []
        self.rpm = 3.0
        self.direction = "CW"
        self.running = True
        self.readbacks = deque()
        self.on_read = None
        self.status_override = {}

    def fields(self, *, valid: bool = True) -> dict:
        return {
            "pump_running": self.running,
            "pump_rpm": self.rpm,
            "pump_direction": self.direction,
            "pump_full_speed": False,
            "pump_readback_valid": valid,
            "pump_bidirectional_supported": True,
        }

    def status(self) -> V2Status:
        self.calls.append(("status",))
        return V2Status(
            **{
                **self.fields(),
                "system_state": "RUNNING" if self.running else "READY",
                "comm_state": "ACTIVE",
                "session_active": True,
                "heartbeat_age_ms": 100,
                "safety": "OK",
                "last_error": "NONE",
                **self.status_override,
            }
        )

    def response(self, command: str, payload: dict) -> V2Response:
        return V2Response(len(self.calls), "OK", command, payload)

    def heater_set_target(self, value: float) -> V2Response:
        return self.response("HEATER_SET_TARGET", {"heater_target_c": value})

    def neopixel_set(self, enabled, brightness, keep_on=None) -> V2Response:
        return self.response("NEOPIXEL_SET", {"neopixel_enabled": enabled})

    def pump_set_rpm(self, rpm: float, direction: str) -> V2Response:
        self.calls.append(("set", rpm, direction))
        self.rpm, self.direction = rpm, direction
        return self.response("PUMP_SET_RPM", self.fields(valid=False))

    def pump_start(self, rpm: float, direction: str) -> V2Response:
        self.calls.append(("start", rpm, direction))
        self.rpm, self.direction, self.running = rpm, direction, True
        return self.response("PUMP_START", self.fields(valid=False))

    def pump_stop(self) -> V2Response:
        self.calls.append(("stop_pump",))
        self.running = False
        self.rpm = 0.1
        return self.response("PUMP_STOP", self.fields(valid=False))

    def stop(self) -> V2Response:
        self.calls.append(("stop_global",))
        self.running = False
        self.rpm = 0.1
        return self.response("STOP", self.fields(valid=False))

    def pump_status(self) -> V2Response:
        self.calls.append(("read",))
        if self.on_read is not None:
            self.on_read()
        result = self.readbacks.popleft() if self.readbacks else {}
        if isinstance(result, Exception):
            raise result
        fields = {} if result is None else {**self.fields(), **result}
        return self.response("PUMP_STATUS", fields)


class PumpSession:
    def __init__(self, client: PumpPeer) -> None:
        self.client = client
        self.state = SessionState.DISCONNECTED
        self.opens = 0

    def open(self) -> V2Status:
        self.state = SessionState.READY
        self.opens += 1
        return self.client.status()

    def stop(self) -> None:
        self.state = SessionState.DISCONNECTED


@pytest.fixture
def pump(tmp_path):
    peer = PumpPeer()
    session = PumpSession(peer)
    controller = AppController(
        V2UiClient(session), StatusCsvLogger(tmp_path / "logs")
    )
    controller.PUMP_UPDATE_INTERVAL_S = 0.0
    controller.PUMP_READBACK_RETRY_S = 0.01
    controller.open_connection()
    controller.prepare_pump_target_rpm(3.0)
    peer.calls.clear()
    yield controller, peer, session
    controller.shutdown()


@pytest.mark.parametrize("sign,direction", [(1, "CW"), (-1, "CCW")])
def test_running_targets_recover_a_missed_rj_without_stop_start(pump, sign, direction):
    controller, peer, _ = pump
    peer.direction = direction
    controller.state.pump.direction = direction
    peer.readbacks.extend([{"pump_readback_valid": False}])

    controller.request_pump_target_rpm(sign * 5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)
    controller.request_pump_target_rpm(sign * 8.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert [call for call in peer.calls if call[0] != "read"] == [
        ("set", 5.0, direction), ("set", 8.0, direction)
    ]
    assert controller.state.pump.readback is True
    assert controller.state.pump.actual_rpm == 8.0
    assert controller.state.last_error == ""
    assert derive_system_status(controller.state) == "RUNNING"


@pytest.mark.parametrize("bad", [None, {"pump_readback_valid": False}])
def test_missing_or_invalid_rj_is_retried_before_another_motion(pump, bad):
    controller, peer, _ = pump
    peer.readbacks.extend([bad, bad])

    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert peer.calls == [("set", 5.0, "CW"), ("read",), ("read",), ("read",)]
    assert controller.state.pump.readback is True
    assert controller.state.pump.actual_rpm == 5.0


@pytest.mark.parametrize("bad", [
    {"pump_rpm": 3.0},
    {"pump_rpm": 100.1},
    {"pump_direction": "CCW"},
    {"pump_running": False},
    {"pump_full_speed": True},
])
def test_valid_but_inconsistent_rj_does_not_confirm_the_sent_setpoint(pump, bad):
    controller, peer, _ = pump
    peer.readbacks.extend([bad, bad, bad])

    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert controller.state.pump.confirmation_error
    assert controller.state.pump.sent_target_rpm == 5.0
    assert controller.state.last_error == ""
    assert [call for call in peer.calls if call[0] == "set"] == [("set", 5.0, "CW")]


def test_persistent_unconfirmed_suspends_then_new_input_can_recover(pump):
    controller, peer, _ = pump
    peer.readbacks.extend([{"pump_readback_valid": False}] * 3)
    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert len(peer.calls) == 4
    assert controller.state.pump.confirmation_error
    assert controller.state.pump.target_rpm == 5.0
    assert controller.state.pump.last_confirmed_rpm == 3.0
    assert derive_system_status(controller.state) == "RUNNING"
    controller.request_pump_target_rpm(8.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert peer.calls == [
        ("set", 5.0, "CW"), ("read",), ("read",), ("read",),
        ("read",), ("set", 8.0, "CW"), ("read",),
    ]
    assert controller.state.pump.confirmation_error == ""
    assert controller.state.pump.actual_rpm == 8.0


def test_latest_target_is_used_after_slow_confirmation_and_ui_poll_does_not_wait(pump):
    controller, peer, _ = pump
    entered, release = threading.Event(), threading.Event()

    def slow_read():
        entered.set()
        assert release.wait(2.0)

    peer.on_read = slow_read
    try:
        controller.request_pump_target_rpm(5.0, allow_restart=True)
        assert entered.wait(0.5)
        started = time.monotonic()
        controller.request_pump_target_rpm(6.0, allow_restart=True)
        controller.request_pump_target_rpm(8.0, allow_restart=True)
        controller.poll_serial()
        elapsed = time.monotonic() - started
    finally:
        release.set()
    assert controller.wait_for_pump_updates(1.0)

    assert elapsed < 0.1
    assert [call for call in peer.calls if call[0] == "set"] == [
        ("set", 5.0, "CW"), ("set", 8.0, "CW")
    ]
    assert controller.state.pump.actual_rpm == 8.0


@pytest.mark.parametrize("cancel", ["stop_pump", "stop_global", "LOST", "FAULT"])
def test_cancellation_during_late_confirmation_never_sends_the_queued_motion(pump, cancel):
    controller, peer, session = pump
    entered, release = threading.Event(), threading.Event()
    peer.on_read = lambda: (entered.set(), release.wait(1.0))
    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert entered.wait(0.5)
    controller.request_pump_target_rpm(8.0, allow_restart=True)
    stop_thread = None
    if cancel == "LOST":
        session.state = SessionState.LOST
        controller._mark_connection_lost("test USB loss")
    elif cancel == "FAULT":
        controller._apply(ParsedMessage(ok=True, is_status=True, fields={"system_state": "FAULT"}))
    else:
        stop_thread = threading.Thread(
            target=controller.stop_pump if cancel == "stop_pump" else controller.stop
        )
        generation = controller.pump_activation_generation
        stop_thread.start()
        deadline = time.monotonic() + 0.5
        while controller.pump_activation_generation == generation:
            assert time.monotonic() < deadline
            time.sleep(0.001)
    release.set()
    if stop_thread:
        stop_thread.join(1.0)
        assert not stop_thread.is_alive()
    assert controller.wait_for_pump_updates(1.0)

    assert [call for call in peer.calls if call[0] == "set"] == [("set", 5.0, "CW")]
    assert not any(call[0] == "start" for call in peer.calls)


def test_unconfirmed_wj_value_is_not_shown_as_the_measured_speed(pump):
    controller, peer, _ = pump
    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller)
    window.timer.stop()
    peer.readbacks.extend([{"pump_readback_valid": False}] * 3)
    controller.request_pump_target_rpm(8.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)
    window.show_pump_page()
    window._render()
    app.processEvents()

    assert "8.0" in window.pump_target_rpm.text()
    assert "8 RPM" not in window.pump_actual_rpm.text()
    assert window.pump_actual_rpm.text() == "Unconfirmed"
    assert "3" in window.pump_info.text()
    assert "unconfirmed" in window.pump_info.text().lower()
    window.close()


def test_real_esp32_error_is_not_retried_or_downgraded(pump):
    controller, peer, _ = pump
    peer.readbacks.append(V2Esp32Error(2, "PUMP_STATUS", "PUMP_RS485_FAILED"))

    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert controller.state.last_error == "PUMP_RS485_FAILED"
    assert derive_system_status(controller.state) == "ERROR"
    assert peer.calls == [("set", 5.0, "CW"), ("read",)]


def test_csv_keeps_raw_values_qualified_by_readback_not_local_confirmation(pump):
    controller, _, _ = pump
    path = controller.start_logging()
    controller._apply(ParsedMessage(
        ok=True, is_status=True, raw="V2 STATUS",
        fields={"pump_rpm": 8.0, "pump_readback_valid": False},
    ))
    controller.stop_logging()

    with path.open(newline="", encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert row["pump_rpm"] == "8.0"
    assert row["pump_readback_valid"] == "False"
    assert row["last_error"] == ""


@pytest.mark.parametrize("direction,target", [("CW", -5.0), ("CCW", 5.0)])
def test_reversal_requires_post_stop_rj_and_starts_exactly_once(pump, direction, target):
    controller, peer, _ = pump
    controller.state.pump.direction = peer.direction = direction
    controller.request_pump_target_rpm(target, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    new_direction = "CCW" if target < 0 else "CW"
    assert peer.calls == [
        ("stop_pump",), ("read",), ("start", 5.0, new_direction), ("read",)
    ]
    assert controller.state.pump.direction == new_direction
    assert controller.state.pump.readback is True


def test_last_pending_value_survives_multiple_rj_failures_and_replaces_obsolete_input(pump):
    controller, peer, _ = pump
    peer.readbacks.extend([{"pump_readback_valid": False}] * 3)
    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)
    entered, release = threading.Event(), threading.Event()
    peer.on_read = lambda: (entered.set(), release.wait(1.0))
    try:
        controller.request_pump_target_rpm(8.0, allow_restart=True)
        assert entered.wait(0.5)
        controller.request_pump_target_rpm(9.0, allow_restart=True)
    finally:
        release.set()
    assert controller.wait_for_pump_updates(1.0)

    assert [call for call in peer.calls if call[0] == "set"] == [
        ("set", 5.0, "CW"), ("set", 9.0, "CW")
    ]
    assert controller.state.pump.target_rpm == 9.0
    assert controller.state.pump.actual_rpm == 9.0


def test_repeated_input_cannot_send_motion_without_a_coherent_recovery_rj(pump):
    controller, peer, _ = pump
    peer.readbacks.extend([{"pump_readback_valid": False}] * 6)
    for target in (5.0, 8.0):
        controller.request_pump_target_rpm(target, allow_restart=True)
        assert controller.wait_for_pump_updates(1.0)

    assert [call for call in peer.calls if call[0] != "read"] == [("set", 5.0, "CW")]
    assert controller.state.pump.target_rpm == 8.0
    assert controller.state.pump.confirmation_pending is False
    assert controller.state.pump.confirmation_error


def test_manual_reconnect_clears_previous_transaction_without_resuming_motion(pump):
    controller, peer, session = pump
    peer.readbacks.extend([{"pump_readback_valid": False}] * 3)
    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)
    assert controller.state.pump.confirmation_error
    session.state = SessionState.LOST
    controller.poll_serial()
    peer.running, peer.rpm = False, 0.1
    peer.calls.clear()

    controller.reconnect()

    assert controller.state.pump.confirmation_error == ""
    assert controller.state.pump.sent_target_rpm is None
    assert controller.state.pump.readback is True
    assert controller.state.pump.running is False
    assert peer.calls == [("status",)]
    assert session.opens == 2


@pytest.mark.parametrize("allow_restart", [False, True])
def test_slider_from_stopped_cannot_authorize_its_own_start(pump, allow_restart):
    controller, peer, _ = pump
    controller.state.pump.running = peer.running = False
    controller.request_pump_target_rpm(8.0, allow_restart=allow_restart)
    assert controller.wait_for_pump_updates(1.0)

    assert controller.state.pump.target_rpm == 8.0
    assert peer.calls == []


def test_slider_release_does_not_repeat_an_already_confirmed_write(pump):
    controller, peer, _ = pump
    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)
    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert peer.calls == [("set", 5.0, "CW"), ("read",)]


def test_zero_setpoint_interrupts_confirmation_retries_instead_of_being_discarded(pump):
    controller, peer, _ = pump
    peer.readbacks.append({"pump_readback_valid": False})

    def request_zero():
        peer.on_read = None
        controller.request_pump_target_rpm(0.0, allow_restart=True)

    peer.on_read = request_zero
    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert peer.calls == [("set", 5.0, "CW"), ("read",), ("stop_pump",), ("read",)]
    assert controller.state.pump.running is False


def test_tenths_resolution_accepts_float_representation_not_another_rpm(pump):
    controller, peer, _ = pump
    peer.readbacks.append({"pump_rpm": 5.100000001})
    controller.request_pump_target_rpm(5.1, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert peer.calls == [("set", 5.1, "CW"), ("read",)]
    assert controller.state.pump.confirmation_error == ""


def test_readback_deadline_stops_retries_even_if_one_response_is_slow(pump):
    controller, peer, _ = pump
    controller.PUMP_READBACK_TIMEOUT_S = 0.02
    peer.on_read = lambda: time.sleep(0.03)
    peer.readbacks.extend([{"pump_readback_valid": False}] * 3)
    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert peer.calls == [("set", 5.0, "CW"), ("read",)]
    assert controller.state.pump.confirmation_error


def test_command_rate_is_measured_from_the_write_even_after_slow_recovery(pump):
    controller, peer, _ = pump
    peer.readbacks.extend([{"pump_readback_valid": False}] * 3)
    controller.request_pump_target_rpm(5.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)
    controller.PUMP_UPDATE_INTERVAL_S = 0.05
    writes = []
    original_set = peer.pump_set_rpm

    def record_write(rpm, direction):
        writes.append(time.monotonic())
        if rpm == 8.0:
            controller.request_pump_target_rpm(9.0, allow_restart=True)
        return original_set(rpm, direction)

    def slow_recovery():
        peer.on_read = None
        time.sleep(0.07)

    peer.pump_set_rpm = record_write
    peer.on_read = slow_recovery
    controller.request_pump_target_rpm(8.0, allow_restart=True)
    assert controller.wait_for_pump_updates(1.0)

    assert len(writes) == 2
    assert writes[1] - writes[0] >= 0.045
    assert controller.state.pump.actual_rpm == 9.0


def test_ui_stop_invalidates_motion_before_its_camera_cleanup(pump, monkeypatch):
    controller, _, _ = pump
    app = QApplication.instance() or QApplication([])
    window = MainWindow(controller)
    window.timer.stop()
    generation = controller.pump_activation_generation
    observed = []
    monkeypatch.setattr(
        window, "_stop_live_video",
        lambda: observed.append(controller.pump_activation_generation != generation),
    )

    window._stop()
    app.processEvents()

    assert observed == [True]
    window.close()


def test_heartbeat_uses_the_same_real_v2_client_between_rj_retries():
    class MemoryPeer:
        is_open = False

        def __init__(self):
            self.commands = []
            self.reply = b""
            self.reads = 0
            self.rpm = 3.0

        def open(self):
            self.is_open = True

        def close(self):
            self.is_open = False

        def write(self, data):
            request = json.loads(data)
            command = request["cmd"]
            self.commands.append(command)
            payload = {"v": 2, "id": request["id"], "type": "OK", "cmd": command}
            if command == "PUMP_SET_RPM":
                self.rpm = request["rpm"]
            if command in {"STATUS", "PUMP_STATUS"}:
                if command == "PUMP_STATUS":
                    self.reads += 1
                payload.update({
                    "type": "STATUS" if command == "STATUS" else "OK",
                    "pump_running": True, "pump_rpm": self.rpm,
                    "pump_direction": "CW", "pump_full_speed": False,
                    "pump_readback_valid": command == "STATUS" or self.reads >= 3,
                    "pump_bidirectional_supported": True,
                    "system_state": "RUNNING", "comm_state": "ACTIVE",
                    "session_active": True, "safety": "OK",
                })
            self.reply = json.dumps(payload).encode() + b"\n"

        def read_line(self, timeout_s):
            return self.reply

    transport = MemoryPeer()
    client = V2Client(transport)
    session = V2Session(client, heartbeat_period_s=0.01)
    controller = AppController(V2UiClient(session))
    controller.PUMP_READBACK_RETRY_S = 0.03
    controller.open_connection()
    try:
        controller.request_pump_target_rpm(5.0, allow_restart=True)
        assert controller.wait_for_pump_updates(1.0)
        commands = transport.commands
        first_read = commands.index("PUMP_STATUS")
        second_read = commands.index("PUMP_STATUS", first_read + 1)
        assert "HEARTBEAT" in commands[first_read + 1:second_read]
        assert controller.state.pump.readback is True
        assert controller.state.pump.actual_rpm == 5.0
        assert session.state is SessionState.READY
    finally:
        controller.shutdown()
