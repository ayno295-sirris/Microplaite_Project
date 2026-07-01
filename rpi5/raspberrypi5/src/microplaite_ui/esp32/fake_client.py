"""Fake ESP32 client for GUI development without hardware."""

from __future__ import annotations

import time

from microplaite_ui.config import DEFAULT_TARGET_C
from microplaite_ui.esp32.client import Esp32Client
from microplaite_ui.esp32.parser import ParsedMessage


class FakeEsp32Client(Esp32Client):
    port = "FAKE"

    def __init__(self) -> None:
        self.temp_c = 24.0
        self.target_c = DEFAULT_TARGET_C
        self.mode = "IDLE"
        self.sensor_valid = True
        self.fault = False
        self.heater_output_percent = 0.0
        self.last_error = ""
        self.pid_limit = 15.0
        self.kp = 8.0
        self.ki = 0.03
        self.kd = 20.0
        self.pump_running = False
        self.pump_rpm = 0.0
        self.pump_full_speed = False
        self.pump_readback = True
        self.neopixel_enabled = True
        self.neopixel_brightness_percent = 50
        self._last_tick = time.monotonic()

    def status(self) -> ParsedMessage:
        self._tick()
        return self._message("OK STATUS")

    def read_temp(self) -> ParsedMessage:
        self._tick()
        return self._message("OK TEMP")

    def clear_error(self) -> ParsedMessage:
        self.last_error = ""
        self.fault = False
        return self._message("OK ERROR CLEARED")

    def set_target(self, temp_c: float) -> ParsedMessage:
        self.target_c = temp_c
        return self._message("OK SET_TARGET")

    def set_pid(self, kp: float, ki: float, kd: float) -> ParsedMessage:
        self.kp, self.ki, self.kd = kp, ki, kd
        return self._message("OK SET_PID")

    def set_pid_limit(self, percent: float) -> ParsedMessage:
        self.pid_limit = percent
        return self._message("OK SET_PID_LIMIT")

    def pid_on(self) -> ParsedMessage:
        self.mode = "PID"
        return self._message("OK PID ON")

    def pid_off(self) -> ParsedMessage:
        self.mode = "IDLE"
        self.heater_output_percent = 0.0
        return self._message("OK PID OFF")

    def stop(self) -> ParsedMessage:
        self.mode = "IDLE"
        self.heater_output_percent = 0.0
        self.pump_running = False
        self.pump_rpm = 0.0
        self.pump_full_speed = False
        return self._message("OK STOP HEATER_OFF")

    def pump_start(self, rpm: float) -> ParsedMessage:
        self.pump_running = True
        self.pump_rpm = max(0.0, min(100.0, round(float(rpm), 1)))
        self.pump_full_speed = False
        return self._message("OK PUMP_START")

    def pump_stop(self) -> ParsedMessage:
        self.pump_running = False
        self.pump_rpm = 0.0
        self.pump_full_speed = False
        return self._message("OK PUMP_STOP")

    def pump_set_rpm(self, rpm: float) -> ParsedMessage:
        self.pump_rpm = max(0.0, min(100.0, round(float(rpm), 1))) if self.pump_running else 0.0
        return self._message("OK PUMP_SET_RPM")

    def pump_prime(self) -> ParsedMessage:
        self.pump_running = True
        self.pump_rpm = 100.0
        self.pump_full_speed = True
        return self._message("OK PUMP_PRIME")

    def pump_status(self) -> ParsedMessage:
        return self._message("OK PUMP_STATUS")

    def neopixel_on(self) -> ParsedMessage:
        self.neopixel_enabled = True
        return self._message("OK NEOPIXEL_ON")

    def neopixel_off(self) -> ParsedMessage:
        self.neopixel_enabled = False
        return self._message("OK NEOPIXEL_OFF")

    def neopixel_brightness(self, percent: int) -> ParsedMessage:
        self.neopixel_brightness_percent = max(0, min(100, int(percent)))
        return self._message("OK NEOPIXEL_BRIGHTNESS")

    def log_on(self, period_ms: int) -> ParsedMessage:
        return self._message(f"OK LOG_ON {period_ms}")

    def log_off(self) -> ParsedMessage:
        return self._message("OK LOG_OFF")

    def send_command(self, command: str) -> ParsedMessage:
        parts = command.strip().split()
        if not parts:
            return self._message("OK")
        name = parts[0].upper()
        if name == "STATUS":
            return self.status()
        if name == "READ_TEMP":
            return self.read_temp()
        if name == "CLEAR_ERROR":
            return self.clear_error()
        if name == "SET_TARGET" and len(parts) >= 2:
            return self.set_target(float(parts[1]))
        if name == "SET_PID" and len(parts) >= 4:
            return self.set_pid(float(parts[1]), float(parts[2]), float(parts[3]))
        if name == "SET_PID_LIMIT" and len(parts) >= 2:
            return self.set_pid_limit(float(parts[1]))
        if name == "PID_ON":
            return self.pid_on()
        if name == "PID_OFF":
            return self.pid_off()
        if name == "STOP":
            return self.stop()
        if name == "PUMP_START" and len(parts) >= 2:
            return self.pump_start(float(parts[1]))
        if name == "PUMP_STOP":
            return self.pump_stop()
        if name == "PUMP_SET_RPM" and len(parts) >= 2:
            return self.pump_set_rpm(float(parts[1]))
        if name == "PUMP_PRIME":
            return self.pump_prime()
        if name == "PUMP_STATUS":
            return self.pump_status()
        if name == "NEOPIXEL_ON":
            return self.neopixel_on()
        if name == "NEOPIXEL_OFF":
            return self.neopixel_off()
        if name == "NEOPIXEL_BRIGHTNESS" and len(parts) >= 2:
            return self.neopixel_brightness(int(float(parts[1])))
        if name == "LOG_ON":
            return self.log_on(int(float(parts[1])) if len(parts) >= 2 else 200)
        if name == "LOG_OFF":
            return self.log_off()
        return self._message(f"OK {command}")

    def read_pending_lines(self) -> list[str]:
        self._tick()
        return [
            "LOG,{time_ms},{temp:.2f},{target:.2f},{heater:.1f},{gpio14},{mode},{sensor},{fault}".format(
                time_ms=int(time.monotonic() * 1000),
                temp=self.temp_c,
                target=self.target_c,
                heater=self.heater_output_percent,
                gpio14="ON" if self.heater_output_percent > 0 else "OFF",
                mode=self.mode,
                sensor=1 if self.sensor_valid else 0,
                fault=1 if self.fault else 0,
            )
        ]

    def read_available(self) -> list[ParsedMessage]:
        self._tick()
        return [self._message("LOG")]

    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(now - self._last_tick, 1.0)
        self._last_tick = now
        if self.mode == "PID":
            error = self.target_c - self.temp_c
            self.heater_output_percent = max(0.0, min(self.pid_limit, error * 4.0))
            self.temp_c += error * min(0.18 * dt, 0.12)
        else:
            self.temp_c += (23.5 - self.temp_c) * min(0.04 * dt, 0.03)

    def _message(self, raw: str) -> ParsedMessage:
        return ParsedMessage(ok=True, raw=raw, lines=[raw], fields=self._fields())

    def _fields(self) -> dict[str, object]:
        return {
            "temp_c": round(self.temp_c, 2),
            "target_c": self.target_c,
            "mode": self.mode,
            "sensor_valid": self.sensor_valid,
            "fault": self.fault,
            "gpio14": self.heater_output_percent > 0,
            "heater_output_percent": round(self.heater_output_percent, 1),
            "safety_limit": 38.0,
            "pid_limit": self.pid_limit,
            "kp": self.kp,
            "ki": self.ki,
            "kd": self.kd,
            "last_error": self.last_error,
            "pump_running": self.pump_running,
            "pump_rpm": self.pump_rpm,
            "pump_full_speed": self.pump_full_speed,
            "pump_readback": self.pump_readback,
            "neopixel_enabled": self.neopixel_enabled,
            "neopixel_brightness_percent": self.neopixel_brightness_percent,
        }
