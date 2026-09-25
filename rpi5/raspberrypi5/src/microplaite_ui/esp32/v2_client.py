"""Transport-independent JSON client for the ESP32 application protocol V2."""

from __future__ import annotations

import json
import math
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from microplaite_ui.esp32.v2_transport import V2Transport

PROTOCOL_VERSION = 2
MAX_REQUEST_BYTES = 160
MAX_RESPONSE_BYTES = 4096


class ProtocolErrorKind(Enum):
    MALFORMED_JSON = "malformed_json"
    INVALID_STRUCTURE = "invalid_structure"
    WRONG_VERSION = "wrong_version"
    INVALID_RESPONSE_TYPE = "invalid_response_type"
    INVALID_FIELD = "invalid_field"
    INVALID_REQUEST = "invalid_request"
    REQUEST_TOO_LARGE = "request_too_large"
    RESPONSE_TOO_LARGE = "response_too_large"


class V2ClientError(RuntimeError):
    """Base error for V2 request handling."""


class V2TimeoutError(V2ClientError):
    """No correlated response arrived before the request deadline."""


class V2ProtocolError(V2ClientError):
    def __init__(self, kind: ProtocolErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class V2Esp32Error(V2ClientError):
    def __init__(self, request_id: int, command: str | None, error: str) -> None:
        super().__init__(error)
        self.request_id = request_id
        self.command = command
        self.error = error


@dataclass(frozen=True, slots=True)
class V2Response:
    request_id: int
    response_type: str
    command: str | None
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class V2Status:
    uptime_ms: int | None = None
    temp_c: float | None = None
    temperature_valid: bool | None = None
    temperature_fault: bool | None = None
    heater_mode: str | None = None
    heater_target_c: float | None = None
    heater_output_percent: float | None = None
    heater_gpio_on: bool | None = None
    safety: Mapping[str, Any] | None = None
    last_error: str | None = None
    error_latched: bool | None = None
    pump_running: bool | None = None
    pump_rpm: float | None = None
    pump_full_speed: bool | None = None
    pump_readback_valid: bool | None = None
    neopixel_enabled: bool | None = None
    neopixel_brightness: int | None = None

    @property
    def confirmed_pump_running(self) -> bool | None:
        if self.pump_readback_valid is not True:
            return None
        return self.pump_running

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> V2Status:
        return cls(
            uptime_ms=_optional_int(payload, "uptime_ms", minimum=0),
            temp_c=_optional_number(payload, "temp_c"),
            temperature_valid=_optional_bool(payload, "temperature_valid"),
            temperature_fault=_optional_bool(payload, "temperature_fault"),
            heater_mode=_optional_string(payload, "heater_mode"),
            heater_target_c=_optional_number(payload, "heater_target_c"),
            heater_output_percent=_optional_number(
                payload,
                "heater_output_percent",
                minimum=0.0,
                maximum=100.0,
            ),
            heater_gpio_on=_optional_bool(payload, "heater_gpio_on"),
            safety=_optional_mapping(payload, "safety"),
            last_error=_optional_string(payload, "last_error"),
            error_latched=_optional_bool(payload, "error_latched"),
            pump_running=_optional_bool(payload, "pump_running"),
            pump_rpm=_optional_number(payload, "pump_rpm", minimum=0.0),
            pump_full_speed=_optional_bool(payload, "pump_full_speed"),
            pump_readback_valid=_optional_bool(payload, "pump_readback_valid"),
            neopixel_enabled=_optional_bool(payload, "neopixel_enabled"),
            neopixel_brightness=_optional_int(
                payload,
                "neopixel_brightness",
                minimum=0,
                maximum=100,
            ),
        )


class V2Client:
    def __init__(
        self,
        transport: V2Transport,
        timeout_s: float = 1.0,
        initial_request_id: int = 1,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if isinstance(initial_request_id, bool) or not isinstance(initial_request_id, int):
            raise TypeError("initial_request_id must be an integer")
        self.transport = transport
        self.timeout_s = float(timeout_s)
        self._next_request_id = initial_request_id
        self._clock = clock
        self._request_lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return self.transport.is_open

    def open(self) -> None:
        self.transport.open()

    def close(self) -> None:
        self.transport.close()

    def ping(self) -> V2Response:
        return self.send_request("PING")

    def status(self) -> V2Status:
        response = self._exchange("STATUS", {}, expected_type="STATUS")
        return V2Status.from_payload(response.payload)

    def stop(self) -> V2Response:
        return self.send_request("STOP")

    def clear_error(self) -> V2Response:
        return self.send_request("CLEAR_ERROR")

    def heater_set_target(self, temp: float) -> V2Response:
        return self.send_request("HEATER_SET_TARGET", target_c=float(temp))

    def heater_set_pid(self, kp: float, ki: float, kd: float) -> V2Response:
        return self.send_request("HEATER_SET_PID", kp=float(kp), ki=float(ki), kd=float(kd))

    def heater_set_pid_limit(self, percent: float) -> V2Response:
        return self.send_request("HEATER_SET_PID_LIMIT", percent=float(percent))

    def heater_set_power_limit(self, percent: float) -> V2Response:
        return self.send_request("HEATER_SET_POWER_LIMIT", percent=float(percent))

    def heater_enable(self, mode: str) -> V2Response:
        return self.send_request("HEATER_ENABLE", mode=str(mode))

    def heater_disable(self) -> V2Response:
        return self.send_request("HEATER_DISABLE")

    def pump_start(self, rpm: float) -> V2Response:
        return self.send_request("PUMP_START", rpm=float(rpm))

    def pump_stop(self) -> V2Response:
        return self.send_request("PUMP_STOP")

    def pump_set_rpm(self, rpm: float) -> V2Response:
        return self.send_request("PUMP_SET_RPM", rpm=float(rpm))

    def pump_prime(self) -> V2Response:
        return self.send_request("PUMP_PRIME")

    def pump_status(self) -> V2Response:
        return self.send_request("PUMP_STATUS")

    def neopixel_set(self, enabled: bool, brightness: int) -> V2Response:
        return self.send_request(
            "NEOPIXEL_SET",
            enabled=bool(enabled),
            brightness=int(brightness),
        )

    def send_request(self, command: str, **fields: Any) -> V2Response:
        return self._exchange(command, fields, expected_type="OK")

    def _exchange(
        self,
        command: str,
        fields: Mapping[str, Any],
        expected_type: str,
    ) -> V2Response:
        with self._request_lock:
            request_id = self._take_request_id()
            encoded = self._serialize_request(request_id, command, fields)
            if not self.transport.is_open:
                self.transport.open()
            self.transport.write(encoded + b"\n")
            return self._read_correlated_response(request_id, expected_type)

    def _take_request_id(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id

    def _serialize_request(
        self,
        request_id: int,
        command: str,
        fields: Mapping[str, Any],
    ) -> bytes:
        reserved_fields = {"v", "id", "cmd"}.intersection(fields)
        if reserved_fields:
            names = ", ".join(sorted(reserved_fields))
            raise V2ProtocolError(
                ProtocolErrorKind.INVALID_REQUEST,
                f"Request fields cannot override reserved keys: {names}",
            )
        request = {"v": PROTOCOL_VERSION, "id": request_id, "cmd": command, **fields}
        try:
            encoded = json.dumps(
                request,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise V2ProtocolError(
                ProtocolErrorKind.INVALID_REQUEST,
                f"Request cannot be serialized: {exc}",
            ) from exc
        if len(encoded) > MAX_REQUEST_BYTES:
            raise V2ProtocolError(
                ProtocolErrorKind.REQUEST_TOO_LARGE,
                f"Serialized request is {len(encoded)} bytes; maximum is {MAX_REQUEST_BYTES}",
            )
        return encoded

    def _read_correlated_response(self, request_id: int, expected_type: str) -> V2Response:
        deadline = self._clock() + self.timeout_s
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise V2TimeoutError(f"Timed out waiting for response id={request_id}")
            line = self.transport.read_line(remaining)
            if line is None:
                raise V2TimeoutError(f"Timed out waiting for response id={request_id}")
            response = self._parse_candidate(line, request_id)
            if response is None:
                continue
            if response.response_type == "ERR":
                error = response.payload.get("error")
                if not isinstance(error, str):
                    raise V2ProtocolError(
                        ProtocolErrorKind.INVALID_FIELD,
                        "ERR response requires a string error field",
                    )
                raise V2Esp32Error(response.request_id, response.command, error)
            if response.response_type != expected_type:
                raise V2ProtocolError(
                    ProtocolErrorKind.INVALID_RESPONSE_TYPE,
                    f"Response id={request_id} has type {response.response_type!r}; expected {expected_type!r}",
                )
            return response

    def _parse_candidate(self, line: bytes, request_id: int) -> V2Response | None:
        content = line.rstrip(b"\r\n")
        if len(content) > MAX_RESPONSE_BYTES:
            raise V2ProtocolError(
                ProtocolErrorKind.RESPONSE_TOO_LARGE,
                f"Response line is {len(content)} bytes; maximum is {MAX_RESPONSE_BYTES}",
            )
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise V2ProtocolError(
                ProtocolErrorKind.MALFORMED_JSON,
                "Response is not valid UTF-8",
            ) from exc
        if not text.lstrip().startswith("{"):
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise V2ProtocolError(
                ProtocolErrorKind.MALFORMED_JSON,
                f"Malformed JSON response: {exc.msg}",
            ) from exc
        if not isinstance(payload, dict):
            raise V2ProtocolError(
                ProtocolErrorKind.INVALID_STRUCTURE,
                "Response must be a JSON object",
            )
        response_id = payload.get("id")
        if isinstance(response_id, bool) or not isinstance(response_id, int):
            raise V2ProtocolError(
                ProtocolErrorKind.INVALID_STRUCTURE,
                "Response requires an integer id",
            )
        if response_id != request_id:
            return None
        if payload.get("v") != PROTOCOL_VERSION:
            raise V2ProtocolError(
                ProtocolErrorKind.WRONG_VERSION,
                f"Response id={request_id} does not use protocol v={PROTOCOL_VERSION}",
            )
        response_type = payload.get("type")
        if response_type not in {"OK", "ERR", "STATUS"}:
            raise V2ProtocolError(
                ProtocolErrorKind.INVALID_RESPONSE_TYPE,
                f"Response id={request_id} has invalid type {response_type!r}",
            )
        command = payload.get("cmd")
        if command is not None and not isinstance(command, str):
            raise V2ProtocolError(
                ProtocolErrorKind.INVALID_FIELD,
                "Response cmd must be a string when present",
            )
        return V2Response(response_id, response_type, command, payload)


def _optional_bool(payload: Mapping[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        _invalid_field(key, "a boolean")
    return value


def _optional_int(
    payload: Mapping[str, Any],
    key: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        _invalid_field(key, "an integer")
    if minimum is not None and value < minimum:
        _invalid_field(key, f">= {minimum}")
    if maximum is not None and value > maximum:
        _invalid_field(key, f"<= {maximum}")
    return value


def _optional_number(
    payload: Mapping[str, Any],
    key: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _invalid_field(key, "a number")
    number = float(value)
    if not math.isfinite(number):
        _invalid_field(key, "a finite number")
    if minimum is not None and number < minimum:
        _invalid_field(key, f">= {minimum}")
    if maximum is not None and number > maximum:
        _invalid_field(key, f"<= {maximum}")
    return number


def _optional_string(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        _invalid_field(key, "a string")
    return value


def _optional_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        _invalid_field(key, "an object")
    return dict(value)


def _invalid_field(key: str, expectation: str) -> None:
    raise V2ProtocolError(
        ProtocolErrorKind.INVALID_FIELD,
        f"STATUS field {key!r} must be {expectation}",
    )
