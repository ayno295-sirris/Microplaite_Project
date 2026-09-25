"""Application controller between GUI and ESP32 client."""

from __future__ import annotations

import threading
from collections import deque
from typing import Callable

from microplaite_ui.config import (
    DEFAULT_LOG_PERIOD_MS,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DEFAULT_PID_LIMIT,
    THERMAL_TEST_MAX_TARGET_C,
)
from microplaite_ui.core.state import AppState
from microplaite_ui.esp32.client import Esp32Client, Esp32ClientError
from microplaite_ui.esp32.parser import ParsedMessage, parse_line


class AppController:
    def __init__(self, client: Esp32Client) -> None:
        self.client = client
        self.state = AppState(port=getattr(client, "port", ""), connected=False)
        self.logs: deque[str] = deque(maxlen=50)
        self._client_lock = threading.RLock()

    def open_connection(self) -> AppState:
        open_session = getattr(self.client, "open_session", None)
        if callable(open_session):
            return self._call(open_session)
        return self.refresh_status()

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
            self.state.connected = False
            self.state.last_error = "ESP32 not connected"
            self.state.last_message = str(exc)
            self.logs.append(str(exc))
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
        return self._call(self.client.stop)

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
        self.state.pump.target_rpm = round(max(0.0, min(100.0, float(rpm))), 1)
        if self.state.pump.running:
            if not self._activation_allowed():
                self._reject_activation()
                return self.state.last_message
            self.state.pump.readback = None
            self._call(lambda: self.client.pump_set_rpm(self.state.pump.target_rpm))
            self._poll_pump_status()
        return self.state.last_message

    def set_pump_rpm(self, rpm: float) -> str:
        return self.set_pump_target_rpm(rpm)

    def start_pump(self) -> str:
        if not self._activation_allowed():
            self._reject_activation()
            return self.state.last_message
        self.state.pump.readback = None
        self._call(lambda: self.client.pump_start(self.state.pump.target_rpm))
        self._poll_pump_status()
        return self.state.last_message

    def stop_pump(self) -> str:
        self.state.pump.readback = None
        self._call(self.client.pump_stop)
        self._poll_pump_status()
        return self.state.last_message

    def prime_pump(self) -> str:
        if not self._activation_allowed():
            self._reject_activation()
            return self.state.last_message
        self.state.pump.readback = None
        self._call(self.client.pump_prime)
        self._poll_pump_status()
        return self.state.last_message

    def shutdown(self) -> None:
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

    def _poll_pump_status(self) -> None:
        if self.state.connected:
            self._call(self.client.pump_status)

    def _call(self, action: Callable[[], ParsedMessage]) -> AppState:
        try:
            with self._client_lock:
                message = action()
            self.state.connected = True
            self._apply(message)
            self._sync_session_state()
        except Esp32ClientError as exc:
            self._mark_connection_lost(str(exc))
        except Exception as exc:
            self.state.connected = False
            self.state.last_message = f"Unexpected error: {exc}"
            if not self.state.last_error:
                self.state.last_error = self.state.last_message
            self.logs.append(self.state.last_message)
        return self.state

    def _sync_session_state(self) -> None:
        session_state = getattr(self.client, "session_state", None)
        if not session_state:
            return
        state_changed = self.state.session_state != str(session_state)
        self.state.session_state = str(session_state)
        if session_state == "LOST" and (state_changed or self.state.connected):
            self._mark_connection_lost("V2 session LOST")

    def _mark_connection_lost(self, message: str) -> None:
        self.state.connected = False
        if self._is_v2:
            self.state.session_state = str(getattr(self.client, "session_state", "LOST"))
            self.state.comm_state = "LOST"
            self.state.session_active = False
        self.state.last_message = message
        self.state.last_error = "ESP32 not connected"
        self.logs.append(message)

    def _apply(self, message: ParsedMessage) -> None:
        for key, value in message.fields.items():
            if hasattr(self.state, key):
                if key == "last_error" and isinstance(value, str) and value.upper() == "NONE":
                    value = ""
                setattr(self.state, key, value)
        if message.error:
            self.state.last_error = message.error
        elif self.state.last_error == "ESP32 not connected":
            self.state.last_error = ""
        if message.is_log and self.state.temp_c is not None:
            time_ms = self.state.time_ms
            if time_ms is None:
                time_ms = len(self.state.temp_history) * DEFAULT_LOG_PERIOD_MS
            self.state.temp_history.append((time_ms, self.state.temp_c))
        self.state.last_message = message.error or message.raw or "OK"
        for line in message.lines or [self.state.last_message]:
            if line:
                self.logs.append(line)
