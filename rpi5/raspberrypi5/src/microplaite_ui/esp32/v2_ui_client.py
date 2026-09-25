"""UI-facing adapter for the supervised ESP32 protocol V2 client."""

from __future__ import annotations

import threading
from collections.abc import Callable

from microplaite_ui.esp32.client import Esp32Client, Esp32ClientError
from microplaite_ui.esp32.parser import ParsedMessage
from microplaite_ui.esp32.v2_client import V2Response, V2Status
from microplaite_ui.esp32.v2_session import SessionState, V2Session

_STATUS_FIELDS = (
    "temp_c",
    "temperature_valid",
    "temperature_fault",
    "heater_mode",
    "heater_target_c",
    "heater_output_percent",
    "heater_gpio_on",
    "safety",
    "last_error",
    "error_latched",
    "pump_running",
    "pump_rpm",
    "pump_full_speed",
    "pump_readback_valid",
    "neopixel_enabled",
    "neopixel_brightness",
    "system_state",
    "comm_state",
    "session_active",
    "heartbeat_age_ms",
)


class V2UiClient(Esp32Client):
    """Expose V2Session/V2Client through the small interface used by the UI."""

    supports_legacy_logging = False
    requires_active_session = True

    def __init__(self, session: V2Session) -> None:
        self.session = session
        self.client = session.client
        self.port = str(getattr(getattr(self.client, "transport", None), "port", ""))
        self._poll_lock = threading.Lock()
        self._poll_thread: threading.Thread | None = None
        self._poll_message: ParsedMessage | None = None
        self._poll_error: Exception | None = None
        self._closing = False

    @property
    def session_state(self) -> str:
        return self.session.state.value

    def open_session(self) -> ParsedMessage:
        self._closing = False
        with self._poll_lock:
            self._poll_message = None
            self._poll_error = None
        return self._run(lambda: self._status_message(self.session.open()))

    def status(self) -> ParsedMessage:
        return self._run(lambda: self._status_message(self.client.status()))

    def clear_error(self) -> ParsedMessage:
        return self._command(self.client.clear_error)

    def set_target(self, temp_c: float) -> ParsedMessage:
        return self._command(lambda: self.client.heater_set_target(temp_c))

    def set_pid(self, kp: float, ki: float, kd: float) -> ParsedMessage:
        return self._command(lambda: self.client.heater_set_pid(kp, ki, kd))

    def set_pid_limit(self, percent: float) -> ParsedMessage:
        return self._command(lambda: self.client.heater_set_pid_limit(percent))

    def set_power_limit(self, percent: float) -> ParsedMessage:
        return self._command(lambda: self.client.heater_set_power_limit(percent))

    def heater_enable(self, mode: str) -> ParsedMessage:
        return self._command(lambda: self.client.heater_enable(mode))

    def pid_on(self) -> ParsedMessage:
        return self.heater_enable("PID")

    def onoff_on(self) -> ParsedMessage:
        return self.heater_enable("ONOFF")

    def pid_off(self) -> ParsedMessage:
        return self._command(self.client.heater_disable)

    def stop(self) -> ParsedMessage:
        return self._command(self.client.stop)

    def pump_start(self, rpm: float) -> ParsedMessage:
        return self._command(lambda: self.client.pump_start(rpm))

    def pump_stop(self) -> ParsedMessage:
        return self._command(self.client.pump_stop)

    def pump_set_rpm(self, rpm: float) -> ParsedMessage:
        return self._command(lambda: self.client.pump_set_rpm(rpm))

    def pump_prime(self) -> ParsedMessage:
        return self._command(self.client.pump_prime)

    def pump_status(self) -> ParsedMessage:
        return self._command(self.client.pump_status)

    def neopixel_set(self, enabled: bool, brightness: int) -> ParsedMessage:
        return self._command(lambda: self.client.neopixel_set(enabled, brightness))

    def read_available(self) -> list[ParsedMessage]:
        if self.session.state is SessionState.LOST:
            raise Esp32ClientError("V2 session LOST")
        if self.session.state is not SessionState.READY or self._closing:
            return []

        with self._poll_lock:
            error = self._poll_error
            self._poll_error = None
            message = self._poll_message
            self._poll_message = None
            if error is None and self._poll_thread is None:
                self._poll_thread = threading.Thread(
                    target=self._poll_status,
                    name="MicroplaiteV2Status",
                    daemon=True,
                )
                self._poll_thread.start()

        if error is not None:
            raise Esp32ClientError(str(error)) from error
        return [message] if message is not None else []

    def close(self) -> None:
        self._closing = True
        with self._poll_lock:
            thread = self._poll_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()
        self.session.stop()

    def _poll_status(self) -> None:
        try:
            message = self._status_message(self.client.status())
        except Exception as exc:  # noqa: BLE001 - preserve any worker failure for the UI thread
            with self._poll_lock:
                self._poll_error = exc
                self._poll_thread = None
            return
        with self._poll_lock:
            self._poll_message = message
            self._poll_thread = None

    def _command(self, action: Callable[[], V2Response]) -> ParsedMessage:
        return self._run(lambda: self._response_message(action()))

    @staticmethod
    def _run(action: Callable[[], ParsedMessage]) -> ParsedMessage:
        try:
            return action()
        except Esp32ClientError:
            raise
        except Exception as exc:
            raise Esp32ClientError(str(exc)) from exc

    def _status_message(self, status: V2Status) -> ParsedMessage:
        fields = {
            name: getattr(status, name)
            for name in _STATUS_FIELDS
            if getattr(status, name) is not None
        }
        fields["session_state"] = self.session_state
        return ParsedMessage(ok=True, fields=fields, raw="V2 STATUS")

    def _response_message(self, response: V2Response) -> ParsedMessage:
        fields = {
            name: response.payload[name]
            for name in _STATUS_FIELDS
            if name in response.payload
        }
        fields["session_state"] = self.session_state
        raw = f"V2 {response.command or response.response_type}"
        return ParsedMessage(ok=True, fields=fields, raw=raw)
