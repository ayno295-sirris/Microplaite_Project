from __future__ import annotations

from collections import deque

import pytest

from microplaite_ui.esp32.v2_serial_transport import SerialV2Transport
from microplaite_ui.esp32.v2_transport import V2TransportError


class FakeSerial:
    def __init__(self, responses: list[bytes], timeout: float) -> None:
        self.responses = deque(responses)
        self.timeout = timeout
        self.is_open = True
        self.writes: list[bytes] = []
        self.flush_count = 0
        self.readline_sizes: list[int] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def flush(self) -> None:
        self.flush_count += 1

    def readline(self, size: int) -> bytes:
        self.readline_sizes.append(size)
        return self.responses.popleft() if self.responses else b""

    def close(self) -> None:
        self.is_open = False


def test_serial_transport_opens_writes_reads_and_closes() -> None:
    created: list[tuple[dict[str, object], FakeSerial]] = []

    def factory(**kwargs):
        serial = FakeSerial([b'{"v":2}\r\n'], float(kwargs["timeout"]))
        created.append((kwargs, serial))
        return serial

    transport = SerialV2Transport(port="/dev/test", serial_factory=factory)

    transport.open()
    transport.write(b'{"v":2}\n')
    line = transport.read_line(0.25)
    transport.close()

    kwargs, serial = created[0]
    assert kwargs == {"port": "/dev/test", "baudrate": 115200, "timeout": 1.0}
    assert serial.writes == [b'{"v":2}\n']
    assert serial.flush_count == 1
    assert serial.readline_sizes == [4098]
    assert line == b'{"v":2}\r\n'
    assert transport.is_open is False


def test_serial_transport_wraps_open_error() -> None:
    def failing_factory(**kwargs):
        raise OSError("port missing")

    transport = SerialV2Transport(port="/dev/missing", serial_factory=failing_factory)

    with pytest.raises(V2TransportError, match="port missing"):
        transport.open()
