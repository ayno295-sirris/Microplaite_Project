"""Small tolerant parser for ESP32 UART lines."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass(slots=True)
class ParsedMessage:
    ok: bool | None = None
    error: str | None = None
    is_log: bool = False
    fields: dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    lines: list[str] = field(default_factory=list)


_KEYS = {
    "temp": "temp_c",
    "temperature": "temp_c",
    "temp_c": "temp_c",
    "target": "target_c",
    "target_c": "target_c",
    "mode": "mode",
    "sensor": "sensor_valid",
    "sensor_valid": "sensor_valid",
    "fault": "fault",
    "gpio14": "gpio14",
    "heater": "heater_output_percent",
    "heater_output": "heater_output_percent",
    "heater_output_percent": "heater_output_percent",
    "output": "heater_output_percent",
    "safety": "safety_limit",
    "safety_limit": "safety_limit",
    "power_limit": "power_limit",
    "kp": "kp",
    "ki": "ki",
    "kd": "kd",
    "pid_kp": "pid_kp",
    "pid_ki": "pid_ki",
    "pid_kd": "pid_kd",
    "pid_limit": "pid_limit",
    "pid_integral": "pid_integral",
    "timeout_remaining": "timeout_remaining_s",
    "timeout_remaining_s": "timeout_remaining_s",
    "last_error": "last_error",
    "error": "last_error",
    "pump_running": "pump_running",
    "pump_rpm": "pump_rpm",
    "pump_full_speed": "pump_full_speed",
    "pump_readback": "pump_readback",
    "neopixel_enabled": "neopixel_enabled",
    "neopixel_brightness": "neopixel_brightness_percent",
}


def parse_line(line: str) -> ParsedMessage:
    raw = line.strip()
    msg = ParsedMessage(raw=raw, lines=[raw])
    if not raw:
        return msg

    upper = raw.upper()
    msg.is_log = upper.startswith("LOG")
    if upper.startswith("ERR"):
        msg.ok = False
        msg.error = raw[3:].strip() or raw
    elif upper.startswith("OK"):
        msg.ok = True

    if upper.startswith("LOG,"):
        msg.fields.update(_parse_csv_log(raw))
        return msg

    body = re.sub(r"^(OK|ERR)\s+", "", raw, flags=re.IGNORECASE)
    if body.upper().startswith("TEMP"):
        value = _first_number(body)
        if value is not None:
            msg.fields["temp_c"] = value
    if "PID ON" in upper:
        msg.fields["mode"] = "PID"
    if "PID OFF" in upper or "STOP" in upper:
        msg.fields["mode"] = "IDLE"
    if "ERROR CLEARED" in upper:
        msg.fields["last_error"] = ""

    msg.fields.update(_parse_pairs(body))
    msg.fields.update(_parse_words(body))
    return msg


def parse_lines(lines: list[str]) -> ParsedMessage:
    merged = ParsedMessage(lines=[line.strip() for line in lines if line.strip()])
    for line in merged.lines:
        parsed = parse_line(line)
        merged.fields.update(parsed.fields)
        if parsed.ok is not None:
            merged.ok = parsed.ok
        if parsed.error:
            merged.error = parsed.error
        if parsed.raw:
            merged.raw = parsed.raw
    return merged


def _parse_pairs(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    chunks = re.split(r"[\s,;]+", text.replace(":", "="))
    for chunk in chunks:
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        name = _KEYS.get(key.strip().lower())
        if name:
            fields[name] = _coerce(value.strip(), name)
    return fields


def _parse_words(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    tokens = [token for token in re.split(r"[\s,;]+", text) if token]
    i = 0
    while i < len(tokens):
        key = tokens[i].upper()
        value = tokens[i + 1] if i + 1 < len(tokens) else ""
        if key in {"OK", "ERR", "STATUS", "LOG"}:
            i += 1
        elif key == "TEMP":
            fields["temp_c"] = _number(value)
            i += 2
        elif key == "SENSOR_VALID":
            fields["sensor_valid"] = _bool(value)
            i += 2
        elif key == "FAULT":
            fields["fault"] = _bool(value)
            i += 2
        elif key == "GPIO14":
            fields["gpio14"] = value.upper()
            i += 2
        elif key == "MODE":
            fields["mode"] = value.upper()
            i += 2
        elif key == "TARGET":
            fields["target_c"] = _number(value)
            i += 2
        elif key == "HEATER_OUTPUT":
            fields["heater_output_percent"] = _number(value)
            i += 2
        elif key == "SAFETY_LIMIT":
            fields["safety_limit"] = _number(value)
            i += 2
        elif key == "POWER_LIMIT":
            fields["power_limit"] = _number(value)
            i += 2
        elif key == "PID" and i + 3 < len(tokens):
            fields["pid_kp"] = fields["kp"] = _number(tokens[i + 1])
            fields["pid_ki"] = fields["ki"] = _number(tokens[i + 2])
            fields["pid_kd"] = fields["kd"] = _number(tokens[i + 3])
            i += 4
        elif key == "PID_LIMIT":
            fields["pid_limit"] = _number(value)
            i += 2
        elif key == "PID_INTEGRAL":
            fields["pid_integral"] = _number(value)
            i += 2
        elif key == "LAST_ERROR":
            fields["last_error"] = value.upper()
            i += 2
        elif key == "TIMEOUT_REMAINING":
            fields["timeout_remaining_s"] = int(_number(value) or 0)
            i += 2
        elif key == "PUMP_RUNNING":
            fields["pump_running"] = _bool(value)
            i += 2
        elif key == "PUMP_RPM":
            fields["pump_rpm"] = _number(value)
            i += 2
        elif key == "PUMP_FULL_SPEED":
            fields["pump_full_speed"] = _bool(value)
            i += 2
        elif key == "PUMP_READBACK":
            fields["pump_readback"] = _bool(value)
            i += 2
        elif key == "NEOPIXEL_ENABLED":
            fields["neopixel_enabled"] = _bool(value)
            i += 2
        elif key == "NEOPIXEL_BRIGHTNESS":
            fields["neopixel_brightness_percent"] = int(_number(value) or 0)
            i += 2
        else:
            i += 1
    return {key: value for key, value in fields.items() if value is not None}


def _parse_csv_log(text: str) -> dict[str, Any]:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) < 9:
        return {}
    return {
        "time_ms": int(_number(parts[1]) or 0),
        "temp_c": _number(parts[2]),
        "target_c": _number(parts[3]),
        "heater_output_percent": _number(parts[4]),
        "gpio14": parts[5].upper(),
        "mode": parts[6].upper(),
        "sensor_valid": _bool(parts[7]),
        "fault": _bool(parts[8]),
    }


def _first_number(text: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def _number(value: str) -> float | None:
    return _first_number(value)


def _bool(value: str) -> bool | None:
    low = value.lower()
    if low in {"1", "true", "yes", "on", "valid"}:
        return True
    if low in {"0", "false", "no", "off", "invalid", "none"}:
        return False
    return None


def _coerce(value: str, name: str) -> Any:
    low = value.lower()
    if name in {"sensor_valid", "fault", "pump_running", "pump_full_speed", "pump_readback", "neopixel_enabled"}:
        parsed = _bool(value)
        if parsed is not None:
            return parsed
    if name == "gpio14":
        return value.upper()
    if name in {
        "temp_c",
        "target_c",
        "heater_output_percent",
        "safety_limit",
        "power_limit",
        "kp",
        "ki",
        "kd",
        "pid_kp",
        "pid_ki",
        "pid_kd",
        "pid_limit",
        "pid_integral",
        "timeout_remaining_s",
        "pump_rpm",
        "neopixel_brightness_percent",
    }:
        return _number(value)
    try:
        return float(value)
    except ValueError:
        return value
