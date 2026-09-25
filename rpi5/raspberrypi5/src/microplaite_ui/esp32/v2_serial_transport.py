"""Pyserial line transport for the ESP32 application protocol V2."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from microplaite_ui.config import DEFAULT_BAUDRATE, default_serial_port
from microplaite_ui.esp32.v2_transport import V2TransportError

DEFAULT_OPEN_TIMEOUT_S = 1.0
DEFAULT_MAX_LINE_BYTES = 4096


class SerialV2Transport:
    def __init__(
        self,
        port: str | None = None,
        baudrate: int = DEFAULT_BAUDRATE,
        open_timeout_s: float = DEFAULT_OPEN_TIMEOUT_S,
        max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
        serial_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.port = port or default_serial_port()
        self.baudrate = baudrate
        self.open_timeout_s = open_timeout_s
        self.max_line_bytes = max_line_bytes
        self._serial_factory = serial_factory
        self._serial: Any | None = None

    @property
    def is_open(self) -> bool:
        return bool(self._serial is not None and self._serial.is_open)

    def open(self) -> None:
        if self.is_open:
            return
        try:
            factory = self._serial_factory
            if factory is None:
                import serial

                factory = serial.Serial
            self._serial = factory(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.open_timeout_s,
            )
        except Exception as exc:
            self._serial = None
            raise V2TransportError(f"Unable to open serial port {self.port}: {exc}") from exc

    def close(self) -> None:
        serial_port = self._serial
        self._serial = None
        if serial_port is None:
            return
        try:
            serial_port.close()
        except Exception as exc:
            raise V2TransportError(f"Unable to close serial port {self.port}: {exc}") from exc

    def write(self, data: bytes) -> None:
        serial_port = self._require_open()
        try:
            serial_port.write(data)
            serial_port.flush()
        except Exception as exc:
            self._close_after_error()
            raise V2TransportError(f"Serial write failed on {self.port}: {exc}") from exc

    def read_line(self, timeout_s: float) -> bytes | None:
        serial_port = self._require_open()
        previous_timeout = serial_port.timeout
        try:
            deadline = time.monotonic() + max(0.0, float(timeout_s))
            line = bytearray()
            # Bound every byte read; pyserial.readline() can restart its timeout per byte.
            while len(line) < self.max_line_bytes + 2:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                serial_port.timeout = remaining
                chunk = serial_port.read(1)
                if not chunk or time.monotonic() >= deadline:
                    return None
                line.extend(chunk)
                if chunk == b"\n":
                    break
            return bytes(line)
        except Exception as exc:
            self._close_after_error()
            raise V2TransportError(f"Serial read failed on {self.port}: {exc}") from exc
        finally:
            if self._serial is serial_port:
                serial_port.timeout = previous_timeout

    def _require_open(self) -> Any:
        if not self.is_open:
            raise V2TransportError(f"Serial port {self.port} is not open")
        return self._serial

    def _close_after_error(self) -> None:
        serial_port = self._serial
        self._serial = None
        if serial_port is None:
            return
        with suppress(Exception):
            serial_port.close()
