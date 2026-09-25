from __future__ import annotations

import json
import threading
from collections import deque

import pytest

from microplaite_ui.esp32.v2_client import (
    ProtocolErrorKind,
    V2Client,
    V2ClientError,
    V2Esp32Error,
    V2ProtocolError,
    V2TimeoutError,
)
from microplaite_ui.esp32.v2_transport import V2TransportError


class MemoryTransport:
    def __init__(self, responses: list[bytes] | None = None) -> None:
        self.responses = deque(responses or [])
        self.writes: list[bytes] = []
        self.read_timeouts: list[float] = []
        self.is_open = False

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def read_line(self, timeout_s: float) -> bytes | None:
        self.read_timeouts.append(timeout_s)
        return self.responses.popleft() if self.responses else None


@pytest.mark.parametrize(
    ("response", "call", "expected_request"),
    [
        (
            b'{"v":2,"id":10,"type":"OK","cmd":"PING"}\n',
            lambda client: client.ping(),
            b'{"v":2,"id":10,"cmd":"PING"}\n',
        ),
        (
            b'{"v":2,"id":10,"type":"OK","cmd":"PUMP_START"}\n',
            lambda client: client.pump_start(3.0),
            b'{"v":2,"id":10,"cmd":"PUMP_START","rpm":3.0}\n',
        ),
        (
            b'{"v":2,"id":10,"type":"OK","cmd":"HEATER_ENABLE"}\n',
            lambda client: client.heater_enable("PID"),
            b'{"v":2,"id":10,"cmd":"HEATER_ENABLE","mode":"PID"}\n',
        ),
        (
            b'{"v":2,"id":10,"type":"OK","cmd":"HEATER_SET_TARGET"}\n',
            lambda client: client.heater_set_target(37.5),
            b'{"v":2,"id":10,"cmd":"HEATER_SET_TARGET","target_c":37.5}\n',
        ),
        (
            b'{"v":2,"id":10,"type":"OK","cmd":"NEOPIXEL_SET"}\n',
            lambda client: client.neopixel_set(True, 35),
            b'{"v":2,"id":10,"cmd":"NEOPIXEL_SET","enabled":true,"brightness":35}\n',
        ),
    ],
)
def test_serializes_v2_commands(
    response: bytes,
    call,
    expected_request: bytes,
) -> None:
    transport = MemoryTransport([response])
    client = V2Client(transport, initial_request_id=10)
    client.open()

    call(client)

    assert transport.writes == [expected_request]


def test_increments_request_id_after_each_request() -> None:
    transport = MemoryTransport(
        [
            b'{"v":2,"id":10,"type":"OK","cmd":"PING"}\n',
            b'{"v":2,"id":11,"type":"OK","cmd":"STOP"}\n',
        ]
    )
    client = V2Client(transport, initial_request_id=10)
    client.open()

    client.ping()
    client.stop()

    assert transport.writes == [
        b'{"v":2,"id":10,"cmd":"PING"}\n',
        b'{"v":2,"id":11,"cmd":"STOP"}\n',
    ]


def test_accepts_response_with_matching_request_id() -> None:
    transport = MemoryTransport([b'{"v":2,"id":10,"type":"OK","cmd":"PING"}\n'])
    client = V2Client(transport, initial_request_id=10)
    client.open()

    response = client.ping()

    assert response.request_id == 10
    assert response.response_type == "OK"
    assert response.command == "PING"


def test_ignores_wrong_request_id_until_matching_response_arrives() -> None:
    transport = MemoryTransport(
        [
            b'{"v":2,"id":9,"type":"OK","cmd":"PING"}\n',
            b'{"v":2,"id":10,"type":"OK","cmd":"PING"}\n',
        ]
    )
    client = V2Client(transport, initial_request_id=10)
    client.open()

    response = client.ping()

    assert response.request_id == 10
    assert len(transport.read_timeouts) == 2


def test_wrong_request_id_times_out_when_no_matching_response_arrives() -> None:
    transport = MemoryTransport([b'{"v":2,"id":9,"type":"OK","cmd":"PING"}\n'])
    client = V2Client(transport, initial_request_id=10, timeout_s=0.01)
    client.open()

    with pytest.raises(V2TimeoutError):
        client.ping()


def test_ignores_legacy_non_json_lines_until_correlated_json_arrives() -> None:
    transport = MemoryTransport(
        [
            b"LOG,100,24.0,37.5,0.0,OFF,IDLE,1,0\r\n",
            b"WARNING legacy warning\n",
            b"ERROR\n",
            b"MAX31856_ERROR\n",
            b'{"v":2,"id":10,"type":"OK","cmd":"PING"}\r\n',
        ]
    )
    client = V2Client(transport, initial_request_id=10)
    client.open()

    response = client.ping()

    assert response.request_id == 10
    assert len(transport.read_timeouts) == 5


def test_rejects_malformed_json_object() -> None:
    transport = MemoryTransport([b'{"v":2,"id":10,}\n'])
    client = V2Client(transport, initial_request_id=10)
    client.open()

    with pytest.raises(V2ProtocolError) as error:
        client.ping()

    assert error.value.kind is ProtocolErrorKind.MALFORMED_JSON


def test_rejects_wrong_protocol_version_for_matching_id() -> None:
    transport = MemoryTransport([b'{"v":3,"id":10,"type":"OK","cmd":"PING"}\n'])
    client = V2Client(transport, initial_request_id=10)
    client.open()

    with pytest.raises(V2ProtocolError) as error:
        client.ping()

    assert error.value.kind is ProtocolErrorKind.WRONG_VERSION


def test_rejects_wrong_response_type_for_matching_id() -> None:
    transport = MemoryTransport([b'{"v":2,"id":10,"type":"STATUS"}\n'])
    client = V2Client(transport, initial_request_id=10)
    client.open()

    with pytest.raises(V2ProtocolError) as error:
        client.ping()

    assert error.value.kind is ProtocolErrorKind.INVALID_RESPONSE_TYPE


def test_raises_distinct_esp32_error_response() -> None:
    transport = MemoryTransport(
        [b'{"v":2,"id":10,"type":"ERR","cmd":"PING","error":"not ready"}\n']
    )
    client = V2Client(transport, initial_request_id=10)
    client.open()

    with pytest.raises(V2Esp32Error) as error:
        client.ping()

    assert error.value.request_id == 10
    assert error.value.command == "PING"
    assert error.value.error == "not ready"


def test_status_parses_known_fields_and_ignores_unknown_fields() -> None:
    payload = {
        "v": 2,
        "id": 10,
        "type": "STATUS",
        "uptime_ms": 1234,
        "temp_c": 24.5,
        "temperature_valid": True,
        "temperature_fault": 0,
        "heater_mode": "PID",
        "heater_target_c": 37.5,
        "heater_output_percent": 12.5,
        "heater_gpio_on": True,
        "safety": "OK",
        "last_error": "NONE",
        "error_latched": False,
        "pump_running": True,
        "pump_rpm": 3.0,
        "pump_full_speed": False,
        "pump_readback_valid": True,
        "neopixel_enabled": True,
        "neopixel_brightness": 35,
        "future_field": "ignored",
    }
    transport = MemoryTransport([(json.dumps(payload, separators=(",", ":")) + "\n").encode()])
    client = V2Client(transport, initial_request_id=10)
    client.open()

    status = client.status()

    assert status.uptime_ms == 1234
    assert status.temp_c == 24.5
    assert status.temperature_valid is True
    assert status.temperature_fault == 0
    assert status.heater_mode == "PID"
    assert status.heater_target_c == 37.5
    assert status.heater_output_percent == 12.5
    assert status.heater_gpio_on is True
    assert status.safety == "OK"
    assert status.last_error == "NONE"
    assert status.error_latched is False
    assert status.pump_running is True
    assert status.pump_rpm == 3.0
    assert status.pump_full_speed is False
    assert status.pump_readback_valid is True
    assert status.confirmed_pump_running is True
    assert status.neopixel_enabled is True
    assert status.neopixel_brightness == 35
    assert not hasattr(status, "future_field")


def test_unconfirmed_pump_readback_keeps_raw_running_value() -> None:
    transport = MemoryTransport(
        [
            b'{"v":2,"id":10,"type":"STATUS","pump_running":false,'
            + b'"pump_rpm":0.0,"pump_full_speed":false,"pump_readback_valid":false}\n'
        ]
    )
    client = V2Client(transport, initial_request_id=10)
    client.open()

    status = client.status()

    assert status.pump_running is False
    assert status.pump_rpm == 0.0
    assert status.pump_full_speed is False
    assert status.pump_readback_valid is False
    assert status.confirmed_pump_running is None


def test_rejects_invalid_present_status_field() -> None:
    transport = MemoryTransport(
        [b'{"v":2,"id":10,"type":"STATUS","pump_rpm":"unknown"}\n']
    )
    client = V2Client(transport, initial_request_id=10)
    client.open()

    with pytest.raises(V2ProtocolError) as error:
        client.status()

    assert error.value.kind is ProtocolErrorKind.INVALID_FIELD


def test_rejects_request_larger_than_160_utf8_bytes_before_write() -> None:
    transport = MemoryTransport()
    client = V2Client(transport, initial_request_id=10)
    client.open()

    with pytest.raises(V2ProtocolError) as error:
        client.send_request("PING", note="é" * 80)

    assert error.value.kind is ProtocolErrorKind.REQUEST_TOO_LARGE
    assert transport.writes == []


def test_rejects_attempt_to_override_reserved_request_fields() -> None:
    transport = MemoryTransport()
    client = V2Client(transport, initial_request_id=10)
    client.open()

    with pytest.raises(V2ProtocolError) as error:
        client.send_request("PING", id=99)

    assert error.value.kind is ProtocolErrorKind.INVALID_REQUEST
    assert transport.writes == []


def test_accepts_status_response_larger_than_request_limit() -> None:
    payload = {
        "v": 2,
        "id": 10,
        "type": "STATUS",
        "last_error": "x" * 300,
    }
    encoded = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
    assert len(encoded.rstrip(b"\r\n")) > 160
    transport = MemoryTransport([encoded])
    client = V2Client(transport, initial_request_id=10)
    client.open()

    status = client.status()

    assert status.last_error == "x" * 300


def test_rejects_response_line_larger_than_4096_bytes() -> None:
    transport = MemoryTransport([b"{" + (b"x" * 4096) + b"}\n"])
    client = V2Client(transport, initial_request_id=10)
    client.open()

    with pytest.raises(V2ProtocolError) as error:
        client.ping()

    assert error.value.kind is ProtocolErrorKind.RESPONSE_TOO_LARGE


class BlockingTransport(MemoryTransport):
    def __init__(self) -> None:
        super().__init__(
            [
                b'{"v":2,"id":10,"type":"OK","cmd":"PING"}\n',
                b'{"v":2,"id":11,"type":"OK","cmd":"PING"}\n',
            ]
        )
        self.first_read_started = threading.Event()
        self.release_first_read = threading.Event()
        self.second_write_attempted = threading.Event()

    def write(self, data: bytes) -> None:
        if self.first_read_started.is_set() and not self.release_first_read.is_set():
            self.second_write_attempted.set()
        super().write(data)

    def read_line(self, timeout_s: float) -> bytes | None:
        if not self.first_read_started.is_set():
            self.first_read_started.set()
            assert self.release_first_read.wait(1.0)
        return super().read_line(timeout_s)


def test_client_allows_only_one_request_in_flight() -> None:
    transport = BlockingTransport()
    client = V2Client(transport, initial_request_id=10)
    client.open()
    errors: list[V2ClientError] = []

    def ping() -> None:
        try:
            client.ping()
        except V2ClientError as exc:  # pragma: no cover - assertion reports the exception
            errors.append(exc)

    first = threading.Thread(target=ping)
    first.start()
    assert transport.first_read_started.wait(1.0)

    second = threading.Thread(target=ping)
    second.start()
    assert not transport.second_write_attempted.wait(0.1)

    transport.release_first_read.set()
    first.join(1.0)
    second.join(1.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert transport.writes == [
        b'{"v":2,"id":10,"cmd":"PING"}\n',
        b'{"v":2,"id":11,"cmd":"PING"}\n',
    ]


@pytest.mark.parametrize("safety", ["OK", "WARNING", "ERROR"])
def test_accepts_real_esp32_status_types(safety) -> None:
    payload = {
        "v": 2, "id": 1, "type": "STATUS",
        "temperature_fault": 0, "safety": safety, "heater_target_c": 37.5,
    }
    client = V2Client(MemoryTransport([json.dumps(payload).encode() + b"\n"]))
    client.open()

    status = client.status()

    assert type(status.temperature_fault) is int
    assert status.temperature_fault == 0
    assert status.safety == safety
    assert status.heater_target_c == 37.5


@pytest.mark.parametrize(
    ("field", "value"),
    [("temperature_fault", True), ("temperature_fault", "0"),
     ("safety", {}), ("safety", "UNKNOWN")],
)
def test_rejects_wrong_esp32_status_types(field, value) -> None:
    payload = {"v": 2, "id": 1, "type": "STATUS", field: value}
    client = V2Client(MemoryTransport([json.dumps(payload).encode() + b"\n"]))
    client.open()

    with pytest.raises(V2ProtocolError) as error:
        client.status()

    assert error.value.kind is ProtocolErrorKind.INVALID_FIELD


@pytest.mark.parametrize("response_type", [[], {}])
def test_rejects_non_string_response_type(response_type) -> None:
    payload = {"v": 2, "id": 1, "type": response_type}
    client = V2Client(MemoryTransport([json.dumps(payload).encode() + b"\n"]))
    client.open()

    with pytest.raises(V2ProtocolError) as error:
        client.ping()

    assert error.value.kind is ProtocolErrorKind.INVALID_RESPONSE_TYPE


def test_rejects_response_returned_after_deadline() -> None:
    now = [0.0]

    class LateTransport(MemoryTransport):
        def read_line(self, timeout_s):
            now[0] += 0.11
            return b'{"v":2,"id":1,"type":"OK"}\n'

    client = V2Client(LateTransport(), timeout_s=0.1, clock=lambda: now[0])
    client.open()

    with pytest.raises(V2TimeoutError):
        client.ping()


@pytest.mark.parametrize("matching_reply", [True, False])
def test_wrong_ids_share_one_deadline(matching_reply) -> None:
    now = [0.0]

    class TimedTransport(MemoryTransport):
        def read_line(self, timeout_s):
            self.read_timeouts.append(timeout_s)
            now[0] += min(0.04, timeout_s)
            reply_id = 1 if matching_reply and len(self.read_timeouts) == 2 else 9
            return json.dumps({"v": 2, "id": reply_id, "type": "OK"}).encode() + b"\n"

    transport = TimedTransport()
    client = V2Client(transport, timeout_s=0.1, clock=lambda: now[0])
    client.open()

    if matching_reply:
        assert client.ping().request_id == 1
        assert now[0] == pytest.approx(0.08)
    else:
        with pytest.raises(V2TimeoutError):
            client.ping()
        assert now[0] == pytest.approx(0.1)
    assert transport.read_timeouts[:2] == pytest.approx([0.1, 0.06])


def test_closed_client_requires_explicit_open() -> None:
    transport = MemoryTransport([b'{"v":2,"id":1,"type":"OK"}\n'])
    client = V2Client(transport)

    with pytest.raises(V2TransportError, match="TRANSPORT_NOT_OPEN"):
        client.ping()

    assert transport.is_open is False
    assert transport.writes == []
