from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from microplaite_ui.core.controller import AppController
from microplaite_ui.core.state import normalize_pump_target_rpm
from microplaite_ui.esp32.client import Esp32ClientError
from microplaite_ui.esp32.fake_client import FakeEsp32Client
from microplaite_ui.esp32.parser import ParsedMessage
from microplaite_ui.esp32.v2_client import V2Esp32Error, V2Response, V2Status
from microplaite_ui.esp32.v2_session import SessionState
from microplaite_ui.esp32.v2_ui_client import V2UiClient
from microplaite_ui.main import create_v2_ui_client
from microplaite_ui.services.recipe_runner import (
    RecipeExecutionError,
    RecipeRunState,
    RecipeStatusSample,
)
from microplaite_ui.services.recipes import RecipeAction, RecipeDefinition, RecipeStep
from microplaite_ui.ui.main_window import MainWindow


class RecordingV2Client:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.status_value = _status()
        self.status_started = threading.Event()
        self.release_status = threading.Event()
        self.block_status = False
        self.status_error: Exception | None = None
        self.pump_status_payload: dict[str, object] = {"pump_readback_valid": True}

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

    def pump_start(self, rpm: float, direction: str | None = None) -> V2Response:
        args = (rpm,) if direction is None else (rpm, direction)
        return self._record("pump_start", *args)

    def pump_stop(self) -> V2Response:
        return self._record("pump_stop")

    def pump_set_rpm(self, rpm: float, direction: str | None = None) -> V2Response:
        args = (rpm,) if direction is None else (rpm, direction)
        return self._record("pump_set_rpm", *args)

    def pump_prime(self) -> V2Response:
        return self._record("pump_prime")

    def pump_status(self) -> V2Response:
        return self._record("pump_status", **self.pump_status_payload)

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


def _recipe(*steps: RecipeStep) -> RecipeDefinition:
    return RecipeDefinition("Test recipe", tuple(steps), Path("test.json"))


def _wait_recipe(controller: AppController, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while controller.recipe_progress.state is RecipeRunState.RUNNING:
        if time.monotonic() >= deadline:
            raise AssertionError("recipe did not reach a terminal state")
        time.sleep(0.005)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (10, 10.0),
        (-10, -10.0),
        (0.14, 0.1),
        (-0.14, -0.1),
        (0.15, 0.2),
        (-0.15, -0.2),
        (0.0, 0.0),
        (-0.0, 0.0),
        (100.0, 100.0),
        (-100.0, -100.0),
    ],
)
def test_normalizes_signed_pump_target_to_one_decimal(value, expected) -> None:
    result = normalize_pump_target_rpm(value)

    assert result == expected
    if expected == 0.0:
        assert str(result) == "0.0"


@pytest.mark.parametrize(
    "value",
    [True, "10", None, float("nan"), float("inf"), float("-inf"), 100.1, -100.1],
)
def test_rejects_invalid_signed_pump_target(value) -> None:
    with pytest.raises((TypeError, ValueError), match="pump target"):
        normalize_pump_target_rpm(value)


@pytest.mark.parametrize("direction", ["CW", "CCW"])
def test_status_propagates_bidirectional_capability_and_reported_direction(
    direction: str,
) -> None:
    controller, client, _ = _ready_controller()
    client.status_value = _status(
        pump_bidirectional_supported=True,
        pump_direction=direction,
        pump_readback_valid=True,
    )

    controller.refresh_status()

    assert controller.state.pump.bidirectional_supported is True
    assert controller.state.pump.direction == direction


def test_status_without_capability_clears_previous_bidirectional_support() -> None:
    controller, client, _ = _ready_controller()
    client.status_value = _status(
        pump_bidirectional_supported=True,
        pump_direction="CCW",
    )
    controller.refresh_status()
    client.status_value = _status(
        pump_bidirectional_supported=None,
        pump_direction=None,
    )

    controller.refresh_status()

    assert controller.state.pump.bidirectional_supported is None
    assert controller.state.pump.direction is None


def test_unconfirmed_status_direction_is_not_kept_as_controller_state() -> None:
    controller, client, _ = _ready_controller()
    client.status_value = _status(
        pump_bidirectional_supported=True,
        pump_direction="CCW",
        pump_readback_valid=False,
    )

    controller.refresh_status()

    assert controller.state.pump.direction is None


def test_old_firmware_positive_start_keeps_legacy_json_shape() -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = None
    controller.state.pump.running = False
    controller.state.pump.readback = True
    client.calls.clear()

    controller.set_pump_target_rpm(10.0)
    controller.start_pump()

    assert client.calls == [("pump_start", 10.0), ("pump_status",)]


def test_old_firmware_rejects_negative_target_without_command() -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = None
    controller.state.pump.running = False
    controller.state.pump.readback = True
    previous_target = controller.state.pump.target_rpm
    client.calls.clear()

    with pytest.raises(ValueError, match="bidirectional"):
        controller.set_pump_target_rpm(-10.0)

    assert controller.state.pump.target_rpm == previous_target
    assert client.calls == []


@pytest.mark.parametrize(
    ("target", "amplitude", "direction"),
    [
        (-100.0, 100.0, "CCW"),
        (-10.0, 10.0, "CCW"),
        (-0.1, 0.1, "CCW"),
        (0.1, 0.1, "CW"),
        (10.0, 10.0, "CW"),
        (100.0, 100.0, "CW"),
    ],
)
def test_bidirectional_start_sends_positive_amplitude_and_direction(
    target: float,
    amplitude: float,
    direction: str,
) -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.running = False
    controller.state.pump.readback = True
    client.calls.clear()

    controller.set_pump_target_rpm(target)
    controller.start_pump()

    assert controller.state.pump.target_rpm == target
    assert client.calls == [("pump_start", amplitude, direction), ("pump_status",)]


@pytest.mark.parametrize(
    ("current_target", "reported_direction", "new_target", "direction"),
    [(5.0, "CW", 10.0, "CW"), (-5.0, "CCW", -10.0, "CCW")],
)
def test_running_same_direction_updates_signed_target(
    current_target: float,
    reported_direction: str,
    new_target: float,
    direction: str,
) -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.target_rpm = current_target
    controller.state.pump.running = True
    controller.state.pump.readback = True
    controller.state.pump.direction = reported_direction
    client.calls.clear()

    controller.set_pump_target_rpm(new_target)

    assert controller.state.pump.target_rpm == new_target
    assert client.calls == [("pump_set_rpm", abs(new_target), direction), ("pump_status",)]


@pytest.mark.parametrize(
    ("current_target", "reported_direction", "new_target"),
    [(10.0, "CW", -10.0), (-10.0, "CCW", 10.0)],
)
def test_running_sign_change_stops_and_requires_fresh_confirmation(
    current_target: float,
    reported_direction: str,
    new_target: float,
) -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.target_rpm = current_target
    controller.state.pump.running = True
    controller.state.pump.readback = True
    controller.state.pump.direction = reported_direction
    client.pump_status_payload = {
        "pump_running": False,
        "pump_rpm": 0.1,
        "pump_readback_valid": True,
        "pump_direction": reported_direction,
    }
    client.calls.clear()

    controller.set_pump_target_rpm(new_target)

    assert controller.state.pump.target_rpm == new_target
    assert controller.state.pump.running is False
    assert controller.state.pump.direction_change_pending is False
    assert client.calls == [("pump_stop",), ("pump_status",)]
    assert not any(call[0] == "pump_start" for call in client.calls)


def test_explicit_start_after_confirmed_sign_change_starts_new_direction() -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.target_rpm = 10.0
    controller.state.pump.running = True
    controller.state.pump.readback = True
    controller.state.pump.direction = "CW"
    client.pump_status_payload = {
        "pump_running": False,
        "pump_readback_valid": True,
        "pump_direction": "CW",
    }

    controller.set_pump_target_rpm(-10.0)
    client.calls.clear()
    controller.start_pump()

    assert client.calls == [("pump_start", 10.0, "CCW"), ("pump_status",)]


@pytest.mark.parametrize(
    "pump_status_payload",
    [
        {"pump_running": False, "pump_readback_valid": False, "pump_direction": "CW"},
        {"pump_running": True, "pump_readback_valid": True, "pump_direction": "CW"},
    ],
)
def test_running_sign_change_stays_blocked_without_fresh_stop_confirmation(
    pump_status_payload: dict[str, object],
) -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.target_rpm = 10.0
    controller.state.pump.running = True
    controller.state.pump.readback = True
    controller.state.pump.direction = "CW"
    client.pump_status_payload = pump_status_payload
    client.calls.clear()

    controller.set_pump_target_rpm(-10.0)
    controller.start_pump()

    assert controller.state.pump.target_rpm == -10.0
    assert controller.state.pump.direction_change_pending is True
    assert "not confirmed" in controller.state.last_error.lower()
    assert client.calls == [("pump_stop",), ("pump_status",)]


def test_running_sign_change_transport_failure_never_starts_inverse_direction() -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.target_rpm = 10.0
    controller.state.pump.running = True
    controller.state.pump.readback = True
    controller.state.pump.direction = "CW"

    def fail_status() -> V2Response:
        client.calls.append(("pump_status",))
        raise RuntimeError("pump status timeout")

    client.pump_status = fail_status
    client.calls.clear()

    controller.set_pump_target_rpm(-10.0)

    assert controller.state.connected is False
    assert controller.state.pump.direction_change_pending is False
    assert "pump status timeout" in controller.state.last_message
    assert client.calls == [("pump_stop",), ("pump_status",)]
    assert not any(call[0] == "pump_start" for call in client.calls)


@pytest.mark.parametrize("stop_kind", ["pump", "global"])
def test_operator_stop_cancels_pending_direction_change(stop_kind: str) -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.direction_change_pending = True
    client.calls.clear()

    if stop_kind == "pump":
        controller.stop_pump()
    else:
        controller.stop()

    assert controller.state.pump.direction_change_pending is False
    expected = [("pump_stop",), ("pump_status",)] if stop_kind == "pump" else [("stop",)]
    assert client.calls == expected
    assert not any(call[0] == "pump_start" for call in client.calls)


def test_lost_and_reconnect_cancel_pending_change_without_resuming_pump() -> None:
    controller, client, session = _ready_controller()
    controller.state.pump.direction_change_pending = True
    session.state = SessionState.LOST

    controller.poll_serial()

    assert controller.state.pump.direction_change_pending is False
    client.status_value = _status(
        pump_running=False,
        pump_readback_valid=True,
        pump_bidirectional_supported=True,
        pump_direction="CW",
        system_state="READY",
    )
    client.calls.clear()
    controller.reconnect()

    assert controller.state.pump.direction_change_pending is False
    assert not any(call[0] == "pump_start" for call in client.calls)


def test_fault_cancels_pending_direction_change() -> None:
    controller, _, _ = _ready_controller()
    controller.state.pump.direction_change_pending = True

    controller._apply(
        ParsedMessage(
            ok=True,
            is_status=True,
            fields={"system_state": "FAULT"},
            raw="V2 STATUS",
        )
    )

    assert controller.state.pump.direction_change_pending is False


@pytest.mark.parametrize("zero", [0.0, -0.0])
def test_zero_target_uses_pump_stop_never_zero_motion_command(zero: float) -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.running = True
    controller.state.pump.readback = True
    controller.state.pump.direction = "CW"
    client.pump_status_payload = {
        "pump_running": False,
        "pump_readback_valid": True,
        "pump_direction": "CW",
    }
    client.calls.clear()

    controller.set_pump_target_rpm(zero)

    assert controller.state.pump.target_rpm == 0.0
    assert client.calls == [("pump_stop",), ("pump_status",)]


def test_prime_refusal_is_reported_without_automatic_stop_or_connection_loss() -> None:
    controller, client, _ = _ready_controller()

    def reject_prime() -> V2Response:
        client.calls.append(("pump_prime",))
        raise V2Esp32Error(12, "PUMP_PRIME", "PUMP_REQUIRES_STOP")

    client.pump_prime = reject_prime
    client.calls.clear()

    controller.prime_pump()

    assert controller.state.connected is True
    assert controller.state.last_error == "PUMP_REQUIRES_STOP"
    assert client.calls == [("pump_prime",), ("pump_status",)]
    assert ("pump_stop",) not in client.calls
    assert ("stop",) not in client.calls


@pytest.mark.parametrize(
    ("step", "expected"),
    [
        (
            RecipeStep(RecipeAction.SET_TEMPERATURE, target_c=44.3),
            [("heater_set_target", 44.3)],
        ),
        (RecipeStep(RecipeAction.HEATER_OFF), [("heater_disable",)]),
        (
            RecipeStep(RecipeAction.PUMP_START, rpm=3.0),
            [("pump_start", 3.0), ("pump_status",)],
        ),
        (
            RecipeStep(RecipeAction.PUMP_SET_RPM, rpm=4.0),
            [("pump_set_rpm", 4.0), ("pump_status",)],
        ),
        (
            RecipeStep(RecipeAction.PUMP_STOP),
            [("pump_stop",), ("pump_status",)],
        ),
        (
            RecipeStep(RecipeAction.PUMP_PRIME),
            [("pump_prime",), ("pump_status",)],
        ),
        (
            RecipeStep(RecipeAction.NEOPIXEL, enabled=True, brightness=35),
            [("neopixel_set", True, 35)],
        ),
    ],
)
def test_recipe_action_maps_to_existing_v2_command(
    step: RecipeStep,
    expected: list[tuple],
) -> None:
    controller, client, _ = _ready_controller()
    client.calls.clear()
    controller.state.pump.running = step.action is RecipeAction.PUMP_SET_RPM
    controller.state.pump.readback = True

    controller.start_recipe(_recipe(step))
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.COMPLETED
    assert client.calls == expected


def test_recipe_negative_start_maps_to_positive_amplitude_and_ccw() -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.running = False
    controller.state.pump.readback = True
    client.calls.clear()

    controller.start_recipe(
        _recipe(RecipeStep(RecipeAction.PUMP_START, rpm=-3.0))
    )
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.COMPLETED
    assert controller.state.pump.target_rpm == -3.0
    assert client.calls == [("pump_start", 3.0, "CCW"), ("pump_status",)]


def test_recipe_negative_target_is_rejected_without_bidirectional_capability() -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = None
    controller.state.pump.running = False
    controller.state.pump.readback = True
    client.calls.clear()

    controller.start_recipe(
        _recipe(RecipeStep(RecipeAction.PUMP_START, rpm=-3.0))
    )
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.ERROR
    assert "bidirectional" in controller.recipe_progress.error
    assert not any(call[0] == "pump_start" for call in client.calls)
    assert client.calls == [("stop",)]


def test_recipe_negative_same_direction_update_uses_ccw() -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.target_rpm = -3.0
    controller.state.pump.running = True
    controller.state.pump.readback = True
    controller.state.pump.direction = "CCW"
    client.calls.clear()

    controller.start_recipe(
        _recipe(RecipeStep(RecipeAction.PUMP_SET_RPM, rpm=-4.0))
    )
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.COMPLETED
    assert client.calls == [("pump_set_rpm", 4.0, "CCW"), ("pump_status",)]


@pytest.mark.parametrize(
    "action",
    [RecipeAction.PUMP_START, RecipeAction.PUMP_SET_RPM],
)
def test_recipe_zero_stops_running_pump_without_zero_motion_command(
    action: RecipeAction,
) -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.running = True
    controller.state.pump.readback = True
    controller.state.pump.direction = "CW"
    client.pump_status_payload = {
        "pump_running": False,
        "pump_readback_valid": True,
        "pump_direction": "CW",
    }
    client.calls.clear()

    controller.start_recipe(_recipe(RecipeStep(action, rpm=0.0)))
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.COMPLETED
    assert client.calls == [("pump_stop",), ("pump_status",)]
    assert not any(call[0] in {"pump_start", "pump_set_rpm"} for call in client.calls)


def test_recipe_sign_change_stops_and_does_not_auto_start() -> None:
    controller, client, _ = _ready_controller()
    controller.state.pump.bidirectional_supported = True
    controller.state.pump.target_rpm = 3.0
    controller.state.pump.running = True
    controller.state.pump.readback = True
    controller.state.pump.direction = "CW"
    client.pump_status_payload = {
        "pump_running": False,
        "pump_readback_valid": True,
        "pump_direction": "CW",
    }
    client.calls.clear()

    controller.start_recipe(
        _recipe(RecipeStep(RecipeAction.PUMP_SET_RPM, rpm=-4.0))
    )
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.COMPLETED
    assert controller.state.pump.target_rpm == -4.0
    assert client.calls == [("pump_stop",), ("pump_status",)]
    assert not any(call[0] == "pump_start" for call in client.calls)


def test_recipe_pid_on_uses_existing_ordered_pid_start_sequence() -> None:
    controller, client, _ = _ready_controller()
    client.calls.clear()

    controller.start_recipe(
        _recipe(
            RecipeStep(RecipeAction.SET_TEMPERATURE, target_c=44.3),
            RecipeStep(RecipeAction.HEATER_PID_ON),
        )
    )
    _wait_recipe(controller)

    assert client.calls == [
        ("heater_set_target", 44.3),
        ("clear_error",),
        ("heater_set_target", 44.3),
        ("heater_set_pid", 8.0, 0.03, 20.0),
        ("heater_set_pid_limit", 15.0),
        ("heater_enable", "PID"),
        ("status",),
    ]


def test_recipe_rejects_legacy_client_before_any_command() -> None:
    client = FakeEsp32Client()
    controller = AppController(client)
    controller.refresh_status()

    with pytest.raises(RecipeExecutionError, match="V2 session"):
        controller.start_recipe(_recipe(RecipeStep(RecipeAction.HEATER_OFF)))

    assert controller.recipe_progress.state is RecipeRunState.STOPPED


def test_only_successful_v2_status_messages_publish_recipe_samples() -> None:
    controller, _, _ = _ready_controller()
    initial_sequence = controller._recipe_status_sequence
    samples: list[RecipeStatusSample] = []
    controller._recipe_runner.publish_status = samples.append

    controller._apply(ParsedMessage(ok=True, raw="V2 PING"))
    controller._apply(
        ParsedMessage(
            ok=False,
            is_status=True,
            raw="V2 STATUS ERROR",
            fields={"temp_c": 44.0, "temperature_valid": True},
        )
    )
    controller._apply(
        ParsedMessage(
            ok=True,
            is_status=True,
            raw="V2 STATUS",
            fields={"temp_c": 44.1, "temperature_valid": True},
        )
    )

    assert [sample.sequence for sample in samples] == [initial_sequence + 1]
    assert samples[0].temp_c == 44.1
    assert samples[0].temperature_valid is True


def test_recipe_status_sample_never_reuses_stale_app_state_temperature() -> None:
    controller, _, _ = _ready_controller()
    initial_sequence = controller._recipe_status_sequence
    controller.state.temp_c = 55.0
    controller.state.temperature_valid = True
    samples: list[RecipeStatusSample] = []
    controller._recipe_runner.publish_status = samples.append

    controller._apply(
        ParsedMessage(ok=True, is_status=True, raw="V2 STATUS", fields={})
    )
    controller._apply(
        ParsedMessage(
            ok=True,
            is_status=True,
            raw="V2 STATUS",
            fields={"temp_c": 44.0},
        )
    )

    assert [sample.sequence for sample in samples] == [
        initial_sequence + 1,
        initial_sequence + 2,
    ]
    assert samples[0].temp_c is None
    assert samples[0].temperature_valid is None
    assert samples[1].temp_c == 44.0
    assert samples[1].temperature_valid is None


def test_legacy_log_does_not_publish_recipe_status_sample() -> None:
    controller = AppController(FakeEsp32Client())
    samples: list[RecipeStatusSample] = []
    controller._recipe_runner.publish_status = samples.append

    controller._apply(
        ParsedMessage(
            ok=True,
            is_log=True,
            raw="LOG,1000,44.3",
            fields={"temp_c": 44.3, "temperature_valid": True},
        )
    )

    assert samples == []


def test_wait_temperature_ignores_pre_wait_status_and_accepts_next_status() -> None:
    controller, _, _ = _ready_controller()
    matching = ParsedMessage(
        ok=True,
        is_status=True,
        raw="V2 STATUS",
        fields={"temp_c": 44.3, "temperature_valid": True},
    )
    controller._apply(matching)

    controller.start_recipe(
        _recipe(
            RecipeStep(
                RecipeAction.WAIT_TEMPERATURE,
                target_c=44.3,
                tolerance_c=0.3,
                timeout_s=1.0,
            )
        )
    )
    deadline = time.monotonic() + 0.2
    while controller.recipe_progress.current_step != "WAIT_TEMPERATURE":
        if time.monotonic() >= deadline:
            raise AssertionError("recipe did not enter WAIT_TEMPERATURE")
        time.sleep(0.005)
    assert controller.recipe_progress.state is RecipeRunState.RUNNING

    controller._apply(matching)
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.COMPLETED


def test_stop_recipe_sets_stopped_before_sending_global_stop() -> None:
    controller, client, _ = _ready_controller()
    observed: list[RecipeRunState] = []
    stop_called = threading.Event()
    original_stop = client.stop

    def observing_stop() -> V2Response:
        observed.append(controller.recipe_progress.state)
        stop_called.set()
        return original_stop()

    client.stop = observing_stop
    client.calls.clear()
    controller.start_recipe(_recipe(RecipeStep(RecipeAction.WAIT, seconds=30.0)))

    controller.stop_recipe()

    assert stop_called.wait(0.2)
    assert observed == [RecipeRunState.STOPPED]
    assert client.calls == [("stop",)]


def test_global_stop_cancels_recipe_before_sending_hardware_stop() -> None:
    controller, client, _ = _ready_controller()
    observed: list[RecipeRunState] = []
    original_stop = client.stop

    def observing_stop() -> V2Response:
        observed.append(controller.recipe_progress.state)
        return original_stop()

    client.stop = observing_stop
    client.calls.clear()
    controller.start_recipe(_recipe(RecipeStep(RecipeAction.WAIT, seconds=30.0)))

    controller.stop()

    assert observed == [RecipeRunState.STOPPED]
    assert client.calls == [("stop",)]


def test_connection_lost_interrupts_recipe_without_hardware_stop() -> None:
    controller, client, session = _ready_controller()
    client.calls.clear()
    controller.start_recipe(_recipe(RecipeStep(RecipeAction.WAIT, seconds=30.0)))

    session.state = SessionState.LOST
    controller.poll_serial()
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.ERROR
    assert controller.recipe_progress.error == "Connection LOST"
    assert ("stop",) not in client.calls


def test_read_available_transport_error_interrupts_recipe_without_stop() -> None:
    controller, client, _ = _ready_controller()
    client.calls.clear()
    controller.start_recipe(_recipe(RecipeStep(RecipeAction.WAIT, seconds=30.0)))

    def fail_read() -> list[ParsedMessage]:
        raise Esp32ClientError("USB disappeared")

    controller.client.read_available = fail_read
    controller.poll_serial()
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.ERROR
    assert ("stop",) not in client.calls


@pytest.mark.parametrize(
    "fault_fields",
    [
        {"system_state": "FAULT"},
        {"safety": "ERROR"},
        {"error_latched": True},
    ],
)
def test_fault_status_interrupts_recipe_before_stop_and_skips_steps(
    fault_fields: dict[str, object],
) -> None:
    controller, client, _ = _ready_controller()
    stop_states: list[RecipeRunState] = []
    stop_called = threading.Event()
    original_stop = client.stop

    def observing_stop() -> V2Response:
        stop_states.append(controller.recipe_progress.state)
        stop_called.set()
        return original_stop()

    client.stop = observing_stop
    client.calls.clear()
    controller.start_recipe(
        _recipe(
            RecipeStep(
                RecipeAction.WAIT_TEMPERATURE,
                target_c=44.3,
                tolerance_c=0.3,
                timeout_s=30.0,
            ),
            RecipeStep(RecipeAction.HEATER_OFF),
        )
    )
    deadline = time.monotonic() + 0.2
    while controller.recipe_progress.current_step != "WAIT_TEMPERATURE":
        if time.monotonic() >= deadline:
            raise AssertionError("recipe did not enter WAIT_TEMPERATURE")
        time.sleep(0.005)

    controller._apply(
        ParsedMessage(
            ok=True,
            is_status=True,
            raw="V2 STATUS",
            fields={
                "temp_c": 44.3,
                "temperature_valid": True,
                **fault_fields,
            },
        )
    )
    _wait_recipe(controller)

    assert controller.recipe_progress.state is RecipeRunState.ERROR
    assert stop_called.wait(0.2)
    assert stop_states == [RecipeRunState.ERROR]
    assert ("heater_disable",) not in client.calls


def test_reconnect_does_not_resume_terminal_recipe() -> None:
    controller, client, session = _ready_controller()
    controller.start_recipe(_recipe(RecipeStep(RecipeAction.WAIT, seconds=30.0)))
    session.state = SessionState.LOST
    controller.poll_serial()
    _wait_recipe(controller)
    client.status_value = _status(system_state="READY", comm_state="ACTIVE")
    client.calls.clear()

    controller.reconnect()
    time.sleep(0.01)

    assert controller.recipe_progress.state is RecipeRunState.ERROR
    assert not any(call[0] in {"heater_enable", "pump_start"} for call in client.calls)


def test_shutdown_stops_recipe_worker_before_closing_client_without_stop() -> None:
    controller, client, _ = _ready_controller()
    states_at_close: list[RecipeRunState] = []
    original_close = controller.client.close

    def observing_close() -> None:
        states_at_close.append(controller.recipe_progress.state)
        original_close()

    controller.client.close = observing_close
    client.calls.clear()
    controller.start_recipe(_recipe(RecipeStep(RecipeAction.WAIT, seconds=30.0)))

    controller.shutdown()

    assert states_at_close == [RecipeRunState.STOPPED]
    assert ("stop",) not in client.calls


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
