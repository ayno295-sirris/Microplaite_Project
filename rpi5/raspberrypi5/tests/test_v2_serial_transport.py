from __future__ import annotations

import io
from collections import deque
from types import SimpleNamespace

import pytest

from microplaite_ui.esp32 import v2_serial_transport
from microplaite_ui.esp32.v2_client import (
    ProtocolErrorKind,
    V2Client,
    V2ProtocolError,
    V2TimeoutError,
)
from microplaite_ui.esp32.v2_serial_transport import SerialV2Transport
from microplaite_ui.esp32.v2_transport import V2TransportError


class FakeSerial(io.RawIOBase):
    def __init__(self, responses: list[bytes], timeout: float) -> None:
        self.responses = deque(responses)
        self.timeout = timeout
        self.is_open = True
        self.writes: list[bytes] = []
        self.flush_count = 0

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def flush(self) -> None:
        self.flush_count += 1

    def read(self, size: int) -> bytes:
        if not self.responses:
            return b""
        data = self.responses.popleft()
        if len(data) > size:
            self.responses.appendleft(data[size:])
        return data[:size]

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
    assert serial.timeout == 1.0
    assert line == b'{"v":2}\r\n'
    assert transport.is_open is False


def test_serial_transport_wraps_open_error() -> None:
    def failing_factory(**kwargs):
        raise OSError("port missing")

    transport = SerialV2Transport(port="/dev/missing", serial_factory=failing_factory)

    with pytest.raises(V2TransportError, match="port missing"):
        transport.open()


def test_slow_serial_response_obeys_global_deadline(monkeypatch) -> None:
    now = [0.0]
    monkeypatch.setattr(v2_serial_transport, "time", SimpleNamespace(monotonic=lambda: now[0]),
                        raising=False)

    class SlowSerial(FakeSerial):
        def read(self, size):
            now[0] += min(0.02, self.timeout)
            if self.timeout < 0.02:
                return b""
            return super().read(size)

    serial = SlowSerial([b'{"v":2,"id":1,"type":"OK"}\n'], timeout=1.0)
    transport = SerialV2Transport(port="/dev/test", serial_factory=lambda **kwargs: serial)
    client = V2Client(transport, timeout_s=0.1, clock=lambda: now[0])
    client.open()

    with pytest.raises(V2TimeoutError):
        client.ping()

    assert now[0] == pytest.approx(0.1)
    assert serial.responses  # The full response was not consumed beyond the deadline.
    assert serial.timeout == 1.0


@pytest.mark.parametrize("operation", ["write", "read"])
def test_transport_failure_requires_explicit_reopen(operation) -> None:
    created = []

    class FailingSerial(FakeSerial):
        def write(self, data):
            if operation == "write":
                raise OSError("disconnected")
            return super().write(data)

        def read(self, size):
            if operation == "read":
                raise OSError("disconnected")
            return super().read(size)

    def factory(**kwargs):
        cls = FailingSerial if not created else FakeSerial
        serial = cls([b'{"v":2,"id":2,"type":"OK"}\n'], float(kwargs["timeout"]))
        created.append(serial)
        return serial

    client = V2Client(SerialV2Transport(port="/dev/test", serial_factory=factory))
    client.open()
    with pytest.raises(V2TransportError, match="disconnected"):
        client.ping()
    assert client.is_open is False
    assert created[0].is_open is False

    with pytest.raises(V2TransportError, match="TRANSPORT_NOT_OPEN"):
        client.ping()
    assert len(created) == 1

    client.open()
    assert client.ping().request_id == 2
    assert len(created) == 2
    client.close()


@pytest.mark.parametrize("size", [4096, 4097])
@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_serial_response_size_limit(size, ending) -> None:
    prefix = b'{"v":2,"id":1,"type":"OK","data":"'
    suffix = b'"}'
    frame = prefix + b"x" * (size - len(prefix) - len(suffix)) + suffix + ending
    serial = FakeSerial([frame], timeout=1.0)
    client = V2Client(SerialV2Transport(port="/dev/test", serial_factory=lambda **kwargs: serial))
    client.open()

    if size == 4096:
        assert client.ping().response_type == "OK"
    else:
        with pytest.raises(V2ProtocolError) as error:
            client.ping()
        assert error.value.kind is ProtocolErrorKind.RESPONSE_TOO_LARGE
    client.close()
