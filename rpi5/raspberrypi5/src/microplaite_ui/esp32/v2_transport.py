"""Transport boundary for the ESP32 application protocol V2."""

from __future__ import annotations

from typing import Protocol


class V2TransportError(RuntimeError):
    """I/O failure raised by a V2 transport."""


class V2Transport(Protocol):
    @property
    def is_open(self) -> bool: ...

    def open(self) -> None: ...

    def close(self) -> None: ...

    def write(self, data: bytes) -> None: ...

    def read_line(self, timeout_s: float) -> bytes | None: ...
