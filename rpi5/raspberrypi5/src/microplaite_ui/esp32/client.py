"""ESP32 client interface."""

from __future__ import annotations

from microplaite_ui.esp32.parser import ParsedMessage


class Esp32ClientError(RuntimeError):
    """Recoverable ESP32 communication error."""


class Esp32Client:
    port: str = ""

    def status(self) -> ParsedMessage:
        raise NotImplementedError

    def read_temp(self) -> ParsedMessage:
        raise NotImplementedError

    def clear_error(self) -> ParsedMessage:
        raise NotImplementedError

    def set_target(self, temp_c: float) -> ParsedMessage:
        raise NotImplementedError

    def set_pid(self, kp: float, ki: float, kd: float) -> ParsedMessage:
        raise NotImplementedError

    def set_pid_limit(self, percent: float) -> ParsedMessage:
        raise NotImplementedError

    def pid_on(self) -> ParsedMessage:
        raise NotImplementedError

    def pid_off(self) -> ParsedMessage:
        raise NotImplementedError

    def stop(self) -> ParsedMessage:
        raise NotImplementedError

    def pump_start(self, rpm: float) -> ParsedMessage:
        raise NotImplementedError

    def pump_stop(self) -> ParsedMessage:
        raise NotImplementedError

    def pump_set_rpm(self, rpm: float) -> ParsedMessage:
        raise NotImplementedError

    def pump_prime(self) -> ParsedMessage:
        raise NotImplementedError

    def pump_status(self) -> ParsedMessage:
        raise NotImplementedError

    def neopixel_on(self) -> ParsedMessage:
        raise NotImplementedError

    def neopixel_off(self) -> ParsedMessage:
        raise NotImplementedError

    def neopixel_brightness(self, percent: int) -> ParsedMessage:
        raise NotImplementedError

    def log_on(self, period_ms: int) -> ParsedMessage:
        raise NotImplementedError

    def log_off(self) -> ParsedMessage:
        raise NotImplementedError

    def send_command(self, command: str) -> ParsedMessage:
        raise NotImplementedError

    def read_pending_lines(self) -> list[str]:
        return []

    def read_available(self) -> list[ParsedMessage]:
        return []

    def close(self) -> None:
        pass
