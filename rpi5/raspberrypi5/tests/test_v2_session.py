from __future__ import annotations

import json
import threading
import time

import pytest

from microplaite_ui.esp32.v2_client import V2Client
from microplaite_ui.esp32.v2_session import SessionState, V2Session
from microplaite_ui.esp32.v2_transport import V2TransportError


class SessionTransport:
    def __init__(self, heartbeat_failure: str | None = None) -> None:
        self.is_open = False
        self.open_count = 0
        self.close_count = 0
        self.writes: list[bytes] = []
        self.heartbeat_failure = heartbeat_failure
        self.heartbeat_attempted = threading.Event()

    @property
    def commands(self) -> list[str]:
        return [json.loads(write)["cmd"] for write in self.writes]

    def open(self) -> None:
        self.is_open = True
        self.open_count += 1

    def close(self) -> None:
        self.is_open = False
        self.close_count += 1

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def read_line(self, timeout_s: float) -> bytes | None:
        request = json.loads(self.writes[-1])
        command = request["cmd"]
        if command == "HEARTBEAT":
            self.heartbeat_attempted.set()
            if self.heartbeat_failure == "timeout":
                return None
            if self.heartbeat_failure == "transport":
                raise V2TransportError("USB disconnected")
            if self.heartbeat_failure == "protocol":
                return _response(request["id"], command, version=3)
        if command == "STATUS":
            return _status_response(request["id"])
        return _response(request["id"], command)


def _response(request_id: int, command: str, version: int = 2) -> bytes:
    payload = {"v": version, "id": request_id, "type": "OK", "cmd": command}
    return json.dumps(payload, separators=(",", ":")).encode() + b"\n"


def _status_response(request_id: int) -> bytes:
    payload = {
        "v": 2,
        "id": request_id,
        "type": "STATUS",
        "cmd": "STATUS",
        "system_state": "IDLE",
        "comm_state": "WAIT_SYNC",
        "session_active": False,
        "heartbeat_age_ms": 0,
    }
    return json.dumps(payload, separators=(",", ":")).encode() + b"\n"


def _wait_for_state(session, expected, timeout_s: float = 0.3) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if session.state is expected:
            return True
        time.sleep(0.005)
    return session.state is expected


def _wait_for_heartbeat_count(
    transport: SessionTransport,
    expected: int,
    timeout_s: float = 0.3,
) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if transport.commands.count("HEARTBEAT") >= expected:
            return True
        time.sleep(0.005)
    return transport.commands.count("HEARTBEAT") >= expected


def test_open_performs_handshake_in_order_and_becomes_ready() -> None:
    transport = SessionTransport()
    session = V2Session(V2Client(transport), heartbeat_period_s=10.0)

    try:
        status = session.open()

        assert transport.commands == ["PING", "STATUS", "SYNC"]
        assert status.system_state == "IDLE"
        assert session.state is SessionState.READY
        assert session.heartbeat_running is True
    finally:
        session.stop()


def test_default_heartbeat_waits_500_ms_before_sending() -> None:
    transport = SessionTransport()
    session = V2Session(V2Client(transport, timeout_s=0.05))

    try:
        session.open()

        assert not transport.heartbeat_attempted.wait(0.3)
        assert transport.heartbeat_attempted.wait(0.4)
        assert transport.commands[:4] == ["PING", "STATUS", "SYNC", "HEARTBEAT"]
    finally:
        session.stop()


def test_heartbeat_repeats_periodically() -> None:
    transport = SessionTransport()
    session = V2Session(
        V2Client(transport, timeout_s=0.05),
        heartbeat_period_s=0.01,
    )

    try:
        session.open()

        assert _wait_for_heartbeat_count(transport, expected=3)
    finally:
        session.stop()


@pytest.mark.parametrize("failure", ["timeout", "transport", "protocol"])
def test_heartbeat_failure_marks_session_lost_and_stops_worker(failure: str) -> None:
    transport = SessionTransport(heartbeat_failure=failure)
    session = V2Session(
        V2Client(transport, timeout_s=0.05),
        heartbeat_period_s=0.01,
    )

    try:
        session.open()

        assert transport.heartbeat_attempted.wait(0.2)
        assert _wait_for_state(session, SessionState.LOST)
        assert session.heartbeat_running is False
    finally:
        session.stop()


def test_lost_session_does_not_reconnect_or_retry() -> None:
    transport = SessionTransport(heartbeat_failure="timeout")
    session = V2Session(
        V2Client(transport, timeout_s=0.05),
        heartbeat_period_s=0.01,
    )

    try:
        session.open()
        assert _wait_for_state(session, SessionState.LOST)
        command_count = len(transport.commands)

        time.sleep(0.05)

        assert session.state is SessionState.LOST
        assert transport.open_count == 1
        assert len(transport.commands) == command_count
        assert transport.commands.count("HEARTBEAT") == 1
    finally:
        session.stop()


def test_explicit_open_recovers_lost_session_with_new_sync() -> None:
    transport = SessionTransport(heartbeat_failure="timeout")
    session = V2Session(
        V2Client(transport, timeout_s=0.05),
        heartbeat_period_s=0.01,
    )

    try:
        session.open()
        assert _wait_for_state(session, SessionState.LOST)
        transport.heartbeat_failure = None

        session.open()

        assert session.state is SessionState.READY
        assert transport.open_count == 2
        assert transport.commands.count("SYNC") == 2
    finally:
        session.stop()


def test_stop_ends_heartbeat_and_closes_without_hardware_stop() -> None:
    transport = SessionTransport()
    session = V2Session(V2Client(transport), heartbeat_period_s=10.0)
    session.open()

    session.stop()

    assert session.state is SessionState.DISCONNECTED
    assert session.heartbeat_running is False
    assert transport.is_open is False
    assert transport.close_count == 1
    assert "STOP" not in transport.commands
