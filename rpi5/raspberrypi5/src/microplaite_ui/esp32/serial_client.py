"""Serial ESP32 client using pyserial."""

from __future__ import annotations

import time

from microplaite_ui.config import DEFAULT_BAUDRATE
from microplaite_ui.esp32.client import Esp32Client, Esp32ClientError
from microplaite_ui.esp32.parser import ParsedMessage, parse_line, parse_lines


class SerialEsp32Client(Esp32Client):
    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE, timeout: float = 0.05) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None

    def status(self) -> ParsedMessage:
        return self.send_command("STATUS")

    def read_temp(self) -> ParsedMessage:
        return self.send_command("READ_TEMP")

    def clear_error(self) -> ParsedMessage:
        return self.send_command("CLEAR_ERROR")

    def set_target(self, temp_c: float) -> ParsedMessage:
        return self.send_command(f"SET_TARGET {temp_c:.2f}")

    def set_pid(self, kp: float, ki: float, kd: float) -> ParsedMessage:
        return self.send_command(f"SET_PID {kp:g} {ki:g} {kd:g}")

    def set_pid_limit(self, percent: float) -> ParsedMessage:
        return self.send_command(f"SET_PID_LIMIT {percent:g}")

    def pid_on(self) -> ParsedMessage:
        return self.send_command("PID_ON")

    def pid_off(self) -> ParsedMessage:
        return self.send_command("PID_OFF")

    def stop(self) -> ParsedMessage:
        return self.send_command("STOP")

    def pump_start(self, rpm: float) -> ParsedMessage:
        return self.send_command(f"PUMP_START {rpm:.1f}")

    def pump_stop(self) -> ParsedMessage:
        return self.send_command("PUMP_STOP")

    def pump_set_rpm(self, rpm: float) -> ParsedMessage:
        return self.send_command(f"PUMP_SET_RPM {rpm:.1f}")

    def pump_prime(self) -> ParsedMessage:
        return self.send_command("PUMP_PRIME")

    def pump_status(self) -> ParsedMessage:
        return self.send_command("PUMP_STATUS")

    def neopixel_on(self) -> ParsedMessage:
        return self.send_command("NEOPIXEL_ON")

    def neopixel_off(self) -> ParsedMessage:
        return self.send_command("NEOPIXEL_OFF")

    def neopixel_brightness(self, percent: int) -> ParsedMessage:
        return self.send_command(f"NEOPIXEL_BRIGHTNESS {percent:d}")

    def log_on(self, period_ms: int) -> ParsedMessage:
        return self.send_command(f"LOG_ON {period_ms}")

    def log_off(self) -> ParsedMessage:
        return self.send_command("LOG_OFF")

    def read_available(self) -> list[ParsedMessage]:
        return [parse_line(line) for line in self.read_pending_lines()]

    def read_pending_lines(self) -> list[str]:
        if self._serial is None or not self._serial.is_open:
            return []
        lines: list[str] = []
        try:
            old_timeout = self._serial.timeout
            self._serial.timeout = 0
            while self._serial.in_waiting:
                line = self._serial.readline().decode("utf-8", errors="replace").strip()
                if line:
                    lines.append(line)
            self._serial.timeout = old_timeout
        except Exception as exc:
            if self._serial is not None:
                self._serial.timeout = self.timeout
            self.close()
            raise Esp32ClientError(f"Serial read error: {exc}") from exc
        return lines

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def _connect(self):
        if self._serial is not None and self._serial.is_open:
            return self._serial
        try:
            import serial

            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            return self._serial
        except Exception as exc:
            raise Esp32ClientError(f"ESP32 not connected on {self.port}: {exc}") from exc

    def send_command(self, command: str) -> ParsedMessage:
        serial_port = self._connect()
        try:
            serial_port.write((command + "\n").encode("utf-8"))
            serial_port.flush()
            return self._read_response(command)
        except Esp32ClientError:
            raise
        except Exception as exc:
            self.close()
            raise Esp32ClientError(f"Serial error during {command}: {exc}") from exc

    def _read_response(self, command: str) -> ParsedMessage:
        assert self._serial is not None
        lines: list[str] = []
        deadline = time.monotonic() + max(1.0, self.timeout * 6)
        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            lines.append(line)
            parsed = parse_line(line)
            if parsed.is_log:
                continue
            if parsed.ok is not None or parsed.error or parsed.fields:
                return parse_lines(lines)
        if lines:
            return parse_lines(lines)
        raise Esp32ClientError(f"ESP32 timeout during {command}")
