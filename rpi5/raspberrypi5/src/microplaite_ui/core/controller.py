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

    def refresh_status(self) -> AppState:
        return self._call(self.client.status)

    def start_live_updates(self) -> AppState:
        if self.state.connected:
            self._call(lambda: self.client.log_on(DEFAULT_LOG_PERIOD_MS))
        return self.state

    def poll_serial(self) -> AppState:
        if not self.state.connected:
            return self.state
        try:
            with self._client_lock:
                read_pending_lines = getattr(self.client, "read_pending_lines", None)
                if callable(read_pending_lines):
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
        self.state.target_c = temp_c
        return self._call(lambda: self.client.set_target(temp_c))

    def set_neopixel_enabled(self, enabled: bool) -> str:
        self.state.neopixel.enabled = enabled
        self._call(self.client.neopixel_on if enabled else self.client.neopixel_off)
        return self.state.last_message

    def set_neopixel_brightness(self, percent: int) -> str:
        self.state.neopixel.brightness_percent = max(0, min(100, int(percent)))
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
            self.state.pump.readback = None
            self._call(lambda: self.client.pump_set_rpm(self.state.pump.target_rpm))
            self._poll_pump_status()
        return self.state.last_message

    def set_pump_rpm(self, rpm: float) -> str:
        return self.set_pump_target_rpm(rpm)

    def start_pump(self) -> str:
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
        self.state.pump.readback = None
        self._call(self.client.pump_prime)
        self._poll_pump_status()
        return self.state.last_message

    def shutdown(self) -> None:
        if self.state.connected:
            try:
                with self._client_lock:
                    self.client.log_off()
            except Esp32ClientError:
                pass
        with self._client_lock:
            self.client.close()

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
        except Esp32ClientError as exc:
            self.state.connected = False
            self.state.last_message = str(exc)
            self.state.last_error = "ESP32 not connected"
            self.logs.append(str(exc))
        except Exception as exc:
            self.state.connected = False
            self.state.last_message = f"Unexpected error: {exc}"
            if not self.state.last_error:
                self.state.last_error = self.state.last_message
            self.logs.append(self.state.last_message)
        return self.state

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
