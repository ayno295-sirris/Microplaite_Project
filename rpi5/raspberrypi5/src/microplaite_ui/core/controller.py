"""Application controller between GUI and ESP32 client."""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

from microplaite_ui.config import (
    DEFAULT_LOG_PERIOD_MS,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DEFAULT_PID_LIMIT,
    THERMAL_TEST_MAX_TARGET_C,
)
from microplaite_ui.core.state import AppState, normalize_pump_target_rpm
from microplaite_ui.esp32.client import Esp32Client, Esp32ClientError
from microplaite_ui.esp32.parser import ParsedMessage, parse_line
from microplaite_ui.services.recipe_runner import (
    RecipeExecutionError,
    RecipeProgress,
    RecipeRunner,
    RecipeStatusSample,
)
from microplaite_ui.services.recipes import RecipeAction, RecipeDefinition, RecipeStep
from microplaite_ui.services.status_csv_logger import StatusCsvLogger


class AppController:
    PUMP_UPDATE_INTERVAL_S = 0.2

    def __init__(self, client: Esp32Client, status_logger: StatusCsvLogger | None = None) -> None:
        self.client = client
        self.state = AppState(port=getattr(client, "port", ""), connected=False)
        self.logs: deque[str] = deque(maxlen=50)
        self._status_logger = status_logger or StatusCsvLogger()
        self.logging_error = ""
        self._client_lock = threading.RLock()
        self._history_clock_start = time.monotonic()
        self._recipe_runner = RecipeRunner(
            execute_command=self._execute_recipe_command,
            global_stop=self._send_recipe_global_stop,
        )
        self._recipe_status_sequence = 0
        self._pump_update_condition = threading.Condition()
        self._pump_pending_update: tuple[float, bool, int] | None = None
        self._pump_update_thread: threading.Thread | None = None
        self._pump_last_update_at = 0.0
        self._pump_activation_generation = 0

    def open_connection(self) -> AppState:
        self._cancel_pump_automation()
        open_session = getattr(self.client, "open_session", None)
        if callable(open_session):
            return self._call(open_session)
        return self.refresh_status()

    def reconnect(self) -> AppState:
        self._cancel_pump_automation()
        reconnect_session = getattr(self.client, "reconnect_session", None)
        if not callable(reconnect_session):
            return self.state
        return self._call(reconnect_session)

    def refresh_status(self) -> AppState:
        if self._is_v2 and getattr(self.client, "session_state", "") != "READY":
            self._sync_session_state()
            return self.state
        return self._call(self.client.status)

    def start_live_updates(self) -> AppState:
        if self.state.connected and getattr(self.client, "supports_legacy_logging", True):
            self._call(lambda: self.client.log_on(DEFAULT_LOG_PERIOD_MS))
        return self.state

    def poll_serial(self) -> AppState:
        self._sync_session_state()
        if not self.state.connected:
            return self.state
        try:
            with self._client_lock:
                read_pending_lines = getattr(self.client, "read_pending_lines", None)
                if self._is_v2:
                    for message in self.client.read_available():
                        self._apply(message)
                elif callable(read_pending_lines):
                    for line in read_pending_lines():
                        self._apply(parse_line(line))
                else:
                    for message in self.client.read_available():
                        self._apply(message)
        except Esp32ClientError as exc:
            self._mark_connection_lost(str(exc))
            return self.state
        return self.state

    def start_pid(self) -> AppState:
        if not self._activation_allowed():
            return self._reject_activation()
        target = self.state.target_c
        for action in (
            self.client.clear_error,
            lambda: self.client.set_target(target),
            lambda: self.client.set_pid(DEFAULT_PID_KP, DEFAULT_PID_KI, DEFAULT_PID_KD),
            lambda: self.client.set_pid_limit(DEFAULT_PID_LIMIT),
            self.client.pid_on,
            self.client.status,
        ):
            self._call(action)
            if not self.state.connected or self.state.last_error:
                break
        return self.state

    def stop_pid(self) -> AppState:
        return self._call(self.client.pid_off)

    def stop(self) -> AppState:
        self._cancel_pump_automation()
        self.cancel_recipe()
        return self._call(self.client.stop)

    def start_recipe(self, recipe: RecipeDefinition) -> None:
        if not self._is_v2 or not self.activation_allowed:
            raise RecipeExecutionError("V2 session is not READY/ACTIVE")
        self._recipe_runner.start(recipe)

    def stop_recipe(self) -> None:
        self._recipe_runner.stop(request_stop=True)

    def cancel_recipe(self, reason: str = "Stopped by operator") -> None:
        self._recipe_runner.stop(reason, request_stop=False)

    @property
    def recipe_progress(self) -> RecipeProgress:
        return self._recipe_runner.snapshot()

    def clear_error(self) -> AppState:
        self._call(self.client.clear_error)
        if self.state.connected:
            self._call(self.client.status)
        return self.state

    def set_target_from_ui(self, temp_c: float) -> AppState:
        self.state.target_c = max(0.0, min(THERMAL_TEST_MAX_TARGET_C, float(temp_c)))
        if not self._activation_allowed():
            return self._reject_activation()
        return self._call(lambda: self.client.set_target(self.state.target_c))

    def set_neopixel_enabled(self, enabled: bool) -> str:
        if enabled and not self._activation_allowed():
            self._reject_activation()
            return self.state.last_message
        self.state.neopixel.enabled = enabled
        neopixel_set = getattr(self.client, "neopixel_set", None)
        if callable(neopixel_set):
            self._call(lambda: neopixel_set(enabled, self.state.neopixel.brightness_percent))
        else:
            self._call(self.client.neopixel_on if enabled else self.client.neopixel_off)
        return self.state.last_message

    def set_neopixel_brightness(self, percent: int) -> str:
        self.state.neopixel.brightness_percent = max(0, min(100, int(percent)))
        if not self._activation_allowed():
            self._reject_activation()
            return self.state.last_message
        neopixel_set = getattr(self.client, "neopixel_set", None)
        if callable(neopixel_set):
            self._call(
                lambda: neopixel_set(
                    self.state.neopixel.enabled,
                    self.state.neopixel.brightness_percent,
                )
            )
        else:
            self._call(lambda: self.client.neopixel_brightness(self.state.neopixel.brightness_percent))
        return self.state.last_message

    def timelapse_neopixel_on(self) -> None:
        self.set_neopixel_enabled(True)

    def timelapse_neopixel_off(self) -> None:
        self.set_neopixel_enabled(False)

    def timelapse_neopixel_brightness(self, percent: int) -> None:
        self.set_neopixel_brightness(percent)

    def set_pump_target_rpm(self, rpm: float) -> str:
        target = self.prepare_pump_target_rpm(rpm)
        generation = self.pump_activation_generation
        return self._apply_prepared_pump_target(
            target,
            allow_restart=False,
            expected_generation=generation,
        )

    def request_pump_target_rpm(
        self,
        rpm: float,
        *,
        allow_restart: bool,
        activation_generation: int | None = None,
    ) -> str:
        target = self.prepare_pump_target_rpm(rpm)
        with self._pump_update_condition:
            generation = self._pump_activation_generation
            if activation_generation is not None and activation_generation != generation:
                allow_restart = False
            self._pump_pending_update = (target, bool(allow_restart), generation)
            thread = self._pump_update_thread
            if thread is None or not thread.is_alive():
                thread = threading.Thread(
                    target=self._run_pump_updates,
                    name="MicroplaitePumpSetpoint",
                    daemon=True,
                )
                self._pump_update_thread = thread
                thread.start()
            self._pump_update_condition.notify_all()
        return self.state.last_message

    @property
    def pump_activation_generation(self) -> int:
        with self._pump_update_condition:
            return self._pump_activation_generation

    def wait_for_pump_updates(self, timeout: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            with self._pump_update_condition:
                thread = self._pump_update_thread
            if thread is None:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return False
            if thread is threading.current_thread():
                return False
            thread.join(remaining)

    def _run_pump_updates(self) -> None:
        try:
            while True:
                with self._pump_update_condition:
                    pending = self._pump_pending_update
                    if pending is None:
                        self._pump_update_thread = None
                        self._pump_update_condition.notify_all()
                        return
                    wait_s = (
                        self._pump_last_update_at
                        + max(0.0, self.PUMP_UPDATE_INTERVAL_S)
                        - time.monotonic()
                    )
                    if wait_s > 0.0:
                        self._pump_update_condition.wait(wait_s)
                        continue
                    self._pump_pending_update = None
                target, allow_restart, generation = pending
                self._apply_prepared_pump_target(
                    target,
                    allow_restart=allow_restart,
                    expected_generation=generation,
                )
                with self._pump_update_condition:
                    self._pump_last_update_at = time.monotonic()
        finally:
            with self._pump_update_condition:
                if self._pump_update_thread is threading.current_thread():
                    self._pump_update_thread = None
                self._pump_update_condition.notify_all()

    def _apply_prepared_pump_target(
        self,
        target: float,
        *,
        allow_restart: bool,
        expected_generation: int,
    ) -> str:
        if not self._pump_generation_is_current(expected_generation):
            return self.state.last_message
        if target == 0.0:
            self._stop_pump_for_setpoint()
            return self.state.last_message
        if not self.state.pump.running:
            if allow_restart:
                self._start_pump_after_zero_crossing(expected_generation)
            return self.state.last_message
        if self.state.pump.readback is not True:
            return self._set_pump_error("Pump readback is unconfirmed; RPM was not applied")
        if not self._activation_allowed():
            self._reject_activation()
            return self.state.last_message

        requested_direction = self._pump_target_direction(target)
        reported_direction = self._reported_pump_direction()
        if reported_direction is None:
            return self._set_pump_error("Pump direction is unconfirmed; RPM was not applied")
        if requested_direction != reported_direction:
            self._stop_for_direction_change(expected_generation)
            return self.state.last_message

        if not self._pump_generation_is_current(expected_generation):
            return self.state.last_message
        self.state.pump.readback = None
        self._call(self._pump_set_rpm_action(abs(target), requested_direction))
        self._poll_pump_status()
        return self.state.last_message

    def prepare_pump_target_rpm(self, rpm: object) -> float:
        target = normalize_pump_target_rpm(rpm)
        if target < 0.0 and self.state.pump.bidirectional_supported is not True:
            raise ValueError("negative pump target requires bidirectional firmware support")
        self.state.pump.target_rpm = target
        return target

    def set_pump_rpm(self, rpm: float) -> str:
        return self.set_pump_target_rpm(rpm)

    def start_pump(self) -> str:
        if not self._activation_allowed():
            self._reject_activation()
            return self.state.last_message
        target = normalize_pump_target_rpm(self.state.pump.target_rpm)
        if target < 0.0 and self.state.pump.bidirectional_supported is not True:
            return self._set_pump_error(
                "Pump bidirectional support is required for a negative target"
            )
        if self.state.pump.direction_change_pending:
            return self._set_pump_error("Pump direction change stop is not confirmed")
        if target == 0.0:
            if self.state.pump.readback is not True or self.state.pump.running:
                return self.stop_pump()
            self.state.last_message = "Pump already stopped"
            return self.state.last_message
        if self._is_v2 and self.state.pump.readback is not True:
            return self._set_pump_error("Pump readback is unconfirmed; START was not sent")
        direction = self._pump_target_direction(target)
        self.state.pump.readback = None
        self._call(self._pump_start_action(abs(target), direction))
        self._poll_pump_status()
        return self.state.last_message

    def stop_pump(self) -> str:
        self._cancel_pump_automation()
        return self._stop_pump_for_setpoint()

    def _stop_pump_for_setpoint(self) -> str:
        self.state.pump.direction_change_pending = False
        self.state.pump.readback = None
        self._call(self.client.pump_stop)
        self._poll_pump_status()
        return self.state.last_message

    def prime_pump(self) -> str:
        self._cancel_pump_automation()
        if not self._activation_allowed():
            self._reject_activation()
            return self.state.last_message
        self.state.pump.readback = None
        self._call(self.client.pump_prime)
        self._poll_pump_status()
        return self.state.last_message

    def _pump_start_action(self, rpm: float, direction: str) -> Callable[[], ParsedMessage]:
        if self.state.pump.bidirectional_supported is True:
            return lambda: self.client.pump_start(rpm, direction)
        return lambda: self.client.pump_start(rpm)

    def _pump_set_rpm_action(self, rpm: float, direction: str) -> Callable[[], ParsedMessage]:
        if self.state.pump.bidirectional_supported is True:
            return lambda: self.client.pump_set_rpm(rpm, direction)
        return lambda: self.client.pump_set_rpm(rpm)

    @staticmethod
    def _pump_target_direction(target: float) -> str:
        return "CW" if target > 0.0 else "CCW"

    def _reported_pump_direction(self) -> str | None:
        if self.state.pump.readback is not True:
            return None
        if self.state.pump.direction in {"CW", "CCW"}:
            return self.state.pump.direction
        if self.state.pump.bidirectional_supported is not True:
            return "CW"
        return None

    def _stop_for_direction_change(self, expected_generation: int) -> None:
        self.state.pump.direction_change_pending = True
        self.state.pump.readback = None
        stop_response = self._call_message(self.client.pump_stop)
        if stop_response is None:
            return
        status_response = self._poll_pump_status()
        if status_response is None:
            return
        fields = status_response.fields
        if (
            fields.get("pump_readback_valid") is not True
            or fields.get("pump_running") is not False
        ):
            self._set_pump_error("Pump direction change stop was not confirmed")
            return
        self.state.pump.direction_change_pending = False
        if self.state.last_error.startswith("Pump direction change"):
            self.state.last_error = ""
        if not self._pump_generation_is_current(expected_generation):
            self.state.last_message = "Pump direction change cancelled"
            return
        with self._pump_update_condition:
            pending = self._pump_pending_update
            if pending is not None and pending[2] == expected_generation:
                target = pending[0]
                self._pump_pending_update = None
            else:
                target = normalize_pump_target_rpm(self.state.pump.target_rpm)
        if target == 0.0:
            self.state.last_message = "Pump stopped at zero setpoint"
            return
        if not self._activation_allowed():
            self.state.last_message = "Pump direction change cancelled: session is not active"
            return
        if target < 0.0 and self.state.pump.bidirectional_supported is not True:
            self._set_pump_error("Pump direction change requires bidirectional support")
            return
        direction = self._pump_target_direction(target)
        self.state.pump.readback = None
        self._call(self._pump_start_action(abs(target), direction))
        self._poll_pump_status()

    def _start_pump_after_zero_crossing(self, expected_generation: int) -> None:
        if not self._pump_generation_is_current(expected_generation):
            return
        if self.state.pump.readback is not True or self.state.pump.running:
            return
        if not self._activation_allowed():
            return
        target = normalize_pump_target_rpm(self.state.pump.target_rpm)
        if target == 0.0:
            return
        if target < 0.0 and self.state.pump.bidirectional_supported is not True:
            return
        direction = self._pump_target_direction(target)
        self.state.pump.readback = None
        self._call(self._pump_start_action(abs(target), direction))
        self._poll_pump_status()

    def _pump_generation_is_current(self, expected_generation: int) -> bool:
        with self._pump_update_condition:
            return expected_generation == self._pump_activation_generation

    def _cancel_pump_automation(self) -> None:
        with self._pump_update_condition:
            self._pump_activation_generation += 1
            self._pump_pending_update = None
            self._pump_update_condition.notify_all()
        self.state.pump.direction_change_pending = False

    def _set_pump_error(self, message: str) -> str:
        self.state.last_message = message
        self.state.last_error = message
        self.logs.append(message)
        return message

    def start_logging(self) -> Path | None:
        try:
            path = self._status_logger.start()
        except OSError as exc:
            self.logging_error = f"Logging unavailable: {exc}"
            self.logs.append(self.logging_error)
            return None
        self.logging_error = ""
        self.logs.append(f"Logging started: {path}")
        return path

    def stop_logging(self) -> None:
        was_active = self._status_logger.active
        try:
            self._status_logger.stop()
        except OSError as exc:
            self.logging_error = f"Logging close failed: {exc}"
            self.logs.append(self.logging_error)
            return
        if was_active:
            self.logs.append("Logging stopped")

    @property
    def logging_active(self) -> bool:
        return self._status_logger.active

    @property
    def logging_path(self) -> Path | None:
        return self._status_logger.path

    def shutdown(self) -> None:
        self._cancel_pump_automation()
        self.wait_for_pump_updates(2.0)
        self._recipe_runner.close()
        self.stop_logging()
        if self.state.connected and getattr(self.client, "supports_legacy_logging", True):
            try:
                with self._client_lock:
                    self.client.log_off()
            except Esp32ClientError:
                pass
        with self._client_lock:
            self.client.close()

    @property
    def activation_allowed(self) -> bool:
        if not self._is_v2:
            return self.state.connected and not bool(self.state.fault)
        return self._activation_allowed()

    @property
    def _is_v2(self) -> bool:
        return bool(getattr(self.client, "requires_active_session", False))

    def _activation_allowed(self) -> bool:
        if not self._is_v2:
            return not bool(self.state.fault)
        return bool(
            self.state.connected
            and self.state.session_state == "READY"
            and self.state.comm_state == "ACTIVE"
            and self.state.system_state in {"READY", "RUNNING"}
            and self.state.safety != "ERROR"
            and not self.state.error_latched
        )

    def _reject_activation(self) -> AppState:
        message = "Activation unavailable: ESP32 V2 session is not READY/ACTIVE"
        self.state.last_message = message
        self.logs.append(message)
        return self.state

    def _log_local_unsupported(self, message: str) -> str:
        self.state.last_message = message
        self.logs.append(message)
        return message

    def _poll_pump_status(self) -> ParsedMessage | None:
        if self.state.connected:
            return self._call_message(self.client.pump_status)
        return None

    def _execute_recipe_command(self, step: RecipeStep) -> None:
        if step.action is RecipeAction.SET_TEMPERATURE:
            if step.target_c is None:
                raise RecipeExecutionError("SET_TEMPERATURE requires target_c")
            self.set_target_from_ui(step.target_c)
        elif step.action is RecipeAction.HEATER_PID_ON:
            self.start_pid()
        elif step.action is RecipeAction.HEATER_OFF:
            self.stop_pid()
        elif step.action is RecipeAction.PUMP_START:
            if step.rpm is None:
                raise RecipeExecutionError("PUMP_START requires rpm")
            self.prepare_pump_target_rpm(step.rpm)
            self.start_pump()
        elif step.action is RecipeAction.PUMP_SET_RPM:
            if step.rpm is None:
                raise RecipeExecutionError("PUMP_SET_RPM requires rpm")
            self.set_pump_target_rpm(step.rpm)
        elif step.action is RecipeAction.PUMP_STOP:
            self.stop_pump()
        elif step.action is RecipeAction.PUMP_PRIME:
            self.prime_pump()
        elif step.action is RecipeAction.NEOPIXEL:
            if step.enabled is None or step.brightness is None:
                raise RecipeExecutionError("NEOPIXEL requires enabled and brightness")
            self.state.neopixel.enabled = step.enabled
            self.state.neopixel.brightness_percent = step.brightness
            self._call(lambda: self.client.neopixel_set(step.enabled, step.brightness))
        else:
            raise RecipeExecutionError(f"unsupported recipe action: {step.action.value}")
        self._check_recipe_command_result()

    def _check_recipe_command_result(self) -> None:
        if (
            not self.state.connected
            or self.state.session_state != "READY"
            or self.state.comm_state != "ACTIVE"
        ):
            self._recipe_runner.fail("Connection LOST", request_stop=False)
            return
        if (
            self.state.system_state == "FAULT"
            or self.state.safety == "ERROR"
            or self.state.error_latched is True
        ):
            self._recipe_runner.fail("ESP32 FAULT", request_stop=True)
            return
        if self.state.last_error:
            raise RecipeExecutionError(self.state.last_error)

    def _send_recipe_global_stop(self) -> None:
        self._cancel_pump_automation()
        self._call(self.client.stop)

    def _call(self, action: Callable[[], ParsedMessage]) -> AppState:
        self._call_message(action)
        return self.state

    def _call_message(self, action: Callable[[], ParsedMessage]) -> ParsedMessage | None:
        try:
            with self._client_lock:
                message = action()
            self.state.connected = True
            self._apply(message)
            self._sync_session_state()
        except Esp32ClientError as exc:
            self._mark_connection_lost(str(exc))
            return None
        except Exception as exc:
            self._cancel_pump_automation()
            self.state.connected = False
            self.state.last_message = f"Unexpected error: {exc}"
            if not self.state.last_error:
                self.state.last_error = self.state.last_message
            self.logs.append(self.state.last_message)
            return None
        return message

    def _sync_session_state(self) -> None:
        session_state = getattr(self.client, "session_state", None)
        if not session_state:
            return
        state_changed = self.state.session_state != str(session_state)
        self.state.session_state = str(session_state)
        if session_state == "LOST" and (state_changed or self.state.connected):
            self._mark_connection_lost("V2 session LOST")

    def _mark_connection_lost(self, message: str) -> None:
        self._cancel_pump_automation()
        self._recipe_runner.fail("Connection LOST", request_stop=False)
        self.stop_logging()
        self.state.connected = False
        if self._is_v2:
            self.state.session_state = str(getattr(self.client, "session_state", "LOST"))
            self.state.comm_state = "LOST"
            self.state.session_active = False
        self.state.last_message = message
        self.state.last_error = "ESP32 not connected"
        self.logs.append(message)

    def _apply(self, message: ParsedMessage) -> None:
        direction = message.fields.get("pump_direction")
        has_direction = "pump_direction" in message.fields
        readback = message.fields.get(
            "pump_readback_valid",
            message.fields.get("pump_readback"),
        )
        for key, value in message.fields.items():
            if key == "pump_direction":
                continue
            if hasattr(self.state, key):
                if key == "last_error" and isinstance(value, str) and value.upper() == "NONE":
                    value = ""
                setattr(self.state, key, value)
        if has_direction:
            self.state.pump_direction = direction if readback is True else None
        elif readback is not None and readback is not True:
            self.state.pump_direction = None
        if (
            self.state.system_state == "FAULT"
            or self.state.safety == "ERROR"
            or self.state.error_latched is True
        ):
            self._cancel_pump_automation()
        if message.is_status and message.ok is True and self._is_v2:
            self._recipe_status_sequence += 1
            sample = RecipeStatusSample(
                sequence=self._recipe_status_sequence,
                received_monotonic=time.monotonic(),
                temperature_valid=message.fields.get("temperature_valid"),
                temp_c=message.fields.get("temp_c"),
            )
            if (
                self.state.system_state == "FAULT"
                or self.state.safety == "ERROR"
                or self.state.error_latched is True
            ):
                self._recipe_runner.fail("ESP32 FAULT", request_stop=True)
            self._recipe_runner.publish_status(sample)
        if message.error:
            self.state.last_error = message.error
        elif self.state.last_error == "ESP32 not connected":
            self.state.last_error = ""
        if message.is_status and message.fields.get("temperature_valid") is True:
            temp_c = message.fields.get("temp_c")
            if temp_c is not None:
                time_ms = message.fields.get("uptime_ms")
                if time_ms is None:
                    time_ms = int((time.monotonic() - self._history_clock_start) * 1000)
                self.state.temp_history.append((int(time_ms), float(temp_c)))
        elif message.is_log and self.state.temp_c is not None:
            time_ms = self.state.time_ms
            if time_ms is None:
                time_ms = len(self.state.temp_history) * DEFAULT_LOG_PERIOD_MS
            self.state.temp_history.append((time_ms, self.state.temp_c))
        if message.is_status and self._is_v2 and self.logging_active:
            try:
                self._status_logger.write_status(self.state)
            except OSError as exc:
                self.logging_error = f"Logging stopped after write failure: {exc}"
                self.logs.append(self.logging_error)
                self.stop_logging()
        self.state.last_message = message.error or message.raw or "OK"
        for line in message.lines or [self.state.last_message]:
            if line:
                self.logs.append(line)
