"""Application state."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from microplaite_ui.config import DEFAULT_TARGET_C

TEMP_HISTORY_MAXLEN = 1500


@dataclass(slots=True)
class ThermalState:
    temp_c: float | None = None
    target_c: float = DEFAULT_TARGET_C
    mode: str = "IDLE"
    sensor_valid: bool | None = None
    fault: bool | None = None
    temperature_fault: int | None = None
    gpio14: str | bool | None = None
    heater_output_percent: float = 0.0
    safety_limit: float | None = None
    power_limit: float | None = None
    pid_limit: float | None = None
    kp: float | None = None
    ki: float | None = None
    kd: float | None = None
    pid_kp: float | None = None
    pid_ki: float | None = None
    pid_kd: float | None = None
    pid_integral: float | None = None
    timeout_remaining_s: int | None = None
    time_ms: int | None = None
    last_error: str = ""
    safety: str | None = None
    error_latched: bool | None = None
    temp_history: deque[tuple[int, float]] = field(
        default_factory=lambda: deque(maxlen=TEMP_HISTORY_MAXLEN)
    )


@dataclass(slots=True)
class PumpState:
    supported: bool = False
    running: bool = False
    actual_rpm: float = 0.0
    target_rpm: float = 50.0
    direction: str = "forward"
    full_speed: bool = False
    readback: bool | None = None


@dataclass(slots=True)
class NeoPixelState:
    supported: bool = False
    enabled: bool = True
    brightness_percent: int = 80


@dataclass(slots=True)
class CameraState:
    supported: bool = False
    available: bool = False
    status: str = "Not available"


@dataclass(slots=True)
class AppState:
    thermal: ThermalState = field(default_factory=ThermalState)
    pump: PumpState = field(default_factory=PumpState)
    neopixel: NeoPixelState = field(default_factory=NeoPixelState)
    camera: CameraState = field(default_factory=CameraState)
    port: str = ""
    connected: bool = False
    last_message: str = ""
    system_state: str | None = None
    comm_state: str | None = None
    session_state: str = "DISCONNECTED"
    session_active: bool | None = None
    heartbeat_age_ms: int | None = None

    @property
    def temp_c(self) -> float | None:
        return self.thermal.temp_c

    @temp_c.setter
    def temp_c(self, value: float | None) -> None:
        self.thermal.temp_c = value

    @property
    def target_c(self) -> float:
        return self.thermal.target_c

    @target_c.setter
    def target_c(self, value: float) -> None:
        self.thermal.target_c = value

    @property
    def mode(self) -> str:
        return self.thermal.mode

    @mode.setter
    def mode(self, value: str) -> None:
        self.thermal.mode = value

    @property
    def sensor_valid(self) -> bool | None:
        return self.thermal.sensor_valid

    @sensor_valid.setter
    def sensor_valid(self, value: bool | None) -> None:
        self.thermal.sensor_valid = value

    @property
    def temperature_valid(self) -> bool | None:
        return self.sensor_valid

    @temperature_valid.setter
    def temperature_valid(self, value: bool | None) -> None:
        self.sensor_valid = value

    @property
    def fault(self) -> bool | None:
        return self.thermal.fault

    @fault.setter
    def fault(self, value: bool | None) -> None:
        self.thermal.fault = value

    @property
    def temperature_fault(self) -> int | None:
        return self.thermal.temperature_fault

    @temperature_fault.setter
    def temperature_fault(self, value: int | None) -> None:
        self.thermal.temperature_fault = value
        self.thermal.fault = None if value is None else value != 0

    @property
    def gpio14(self) -> str | bool | None:
        return self.thermal.gpio14

    @gpio14.setter
    def gpio14(self, value: str | bool | None) -> None:
        self.thermal.gpio14 = value

    @property
    def heater_gpio_on(self) -> bool | None:
        value = self.gpio14
        return value if isinstance(value, bool) else None

    @heater_gpio_on.setter
    def heater_gpio_on(self, value: bool | None) -> None:
        self.gpio14 = value

    @property
    def heater_mode(self) -> str:
        return self.mode

    @heater_mode.setter
    def heater_mode(self, value: str) -> None:
        self.mode = value

    @property
    def heater_target_c(self) -> float:
        return self.target_c

    @heater_target_c.setter
    def heater_target_c(self, value: float) -> None:
        self.target_c = value

    @property
    def heater_output_percent(self) -> float:
        return self.thermal.heater_output_percent

    @heater_output_percent.setter
    def heater_output_percent(self, value: float) -> None:
        self.thermal.heater_output_percent = value

    @property
    def safety_limit(self) -> float | None:
        return self.thermal.safety_limit

    @safety_limit.setter
    def safety_limit(self, value: float | None) -> None:
        self.thermal.safety_limit = value

    @property
    def power_limit(self) -> float | None:
        return self.thermal.power_limit

    @power_limit.setter
    def power_limit(self, value: float | None) -> None:
        self.thermal.power_limit = value

    @property
    def pid_limit(self) -> float | None:
        return self.thermal.pid_limit

    @pid_limit.setter
    def pid_limit(self, value: float | None) -> None:
        self.thermal.pid_limit = value

    @property
    def kp(self) -> float | None:
        return self.thermal.kp

    @kp.setter
    def kp(self, value: float | None) -> None:
        self.thermal.kp = value

    @property
    def ki(self) -> float | None:
        return self.thermal.ki

    @ki.setter
    def ki(self, value: float | None) -> None:
        self.thermal.ki = value

    @property
    def kd(self) -> float | None:
        return self.thermal.kd

    @kd.setter
    def kd(self, value: float | None) -> None:
        self.thermal.kd = value

    @property
    def pid_kp(self) -> float | None:
        return self.thermal.pid_kp

    @pid_kp.setter
    def pid_kp(self, value: float | None) -> None:
        self.thermal.pid_kp = value

    @property
    def pid_ki(self) -> float | None:
        return self.thermal.pid_ki

    @pid_ki.setter
    def pid_ki(self, value: float | None) -> None:
        self.thermal.pid_ki = value

    @property
    def pid_kd(self) -> float | None:
        return self.thermal.pid_kd

    @pid_kd.setter
    def pid_kd(self, value: float | None) -> None:
        self.thermal.pid_kd = value

    @property
    def pid_integral(self) -> float | None:
        return self.thermal.pid_integral

    @pid_integral.setter
    def pid_integral(self, value: float | None) -> None:
        self.thermal.pid_integral = value

    @property
    def timeout_remaining_s(self) -> int | None:
        return self.thermal.timeout_remaining_s

    @timeout_remaining_s.setter
    def timeout_remaining_s(self, value: int | None) -> None:
        self.thermal.timeout_remaining_s = value

    @property
    def time_ms(self) -> int | None:
        return self.thermal.time_ms

    @time_ms.setter
    def time_ms(self, value: int | None) -> None:
        self.thermal.time_ms = value

    @property
    def uptime_ms(self) -> int | None:
        return self.time_ms

    @uptime_ms.setter
    def uptime_ms(self, value: int | None) -> None:
        self.time_ms = value

    @property
    def last_error(self) -> str:
        return self.thermal.last_error

    @last_error.setter
    def last_error(self, value: str) -> None:
        self.thermal.last_error = value

    @property
    def safety(self) -> str | None:
        return self.thermal.safety

    @safety.setter
    def safety(self, value: str | None) -> None:
        self.thermal.safety = value

    @property
    def error_latched(self) -> bool | None:
        return self.thermal.error_latched

    @error_latched.setter
    def error_latched(self, value: bool | None) -> None:
        self.thermal.error_latched = value

    @property
    def temp_history(self) -> deque[tuple[int, float]]:
        return self.thermal.temp_history

    @property
    def pump_running(self) -> bool:
        return self.pump.running

    @pump_running.setter
    def pump_running(self, value: bool) -> None:
        self.pump.supported = True
        self.pump.running = bool(value)

    @property
    def pump_rpm(self) -> float:
        return float(self.pump.actual_rpm)

    @pump_rpm.setter
    def pump_rpm(self, value: float) -> None:
        self.pump.supported = True
        self.pump.actual_rpm = round(float(value), 1)

    @property
    def pump_full_speed(self) -> bool:
        return self.pump.full_speed

    @pump_full_speed.setter
    def pump_full_speed(self, value: bool) -> None:
        self.pump.supported = True
        self.pump.full_speed = bool(value)

    @property
    def pump_readback(self) -> bool | None:
        return self.pump.readback

    @pump_readback.setter
    def pump_readback(self, value: bool | None) -> None:
        self.pump.supported = True
        self.pump.readback = value

    @property
    def pump_readback_valid(self) -> bool | None:
        return self.pump_readback

    @pump_readback_valid.setter
    def pump_readback_valid(self, value: bool | None) -> None:
        self.pump_readback = value

    @property
    def neopixel_enabled(self) -> bool:
        return self.neopixel.enabled

    @neopixel_enabled.setter
    def neopixel_enabled(self, value: bool) -> None:
        self.neopixel.supported = True
        self.neopixel.enabled = bool(value)

    @property
    def neopixel_brightness_percent(self) -> int:
        return self.neopixel.brightness_percent

    @neopixel_brightness_percent.setter
    def neopixel_brightness_percent(self, value: int | float) -> None:
        self.neopixel.supported = True
        self.neopixel.brightness_percent = max(0, min(100, int(round(float(value)))))

    @property
    def neopixel_brightness(self) -> int:
        return self.neopixel_brightness_percent

    @neopixel_brightness.setter
    def neopixel_brightness(self, value: int | float) -> None:
        self.neopixel_brightness_percent = value


def derive_system_status(state: AppState) -> str:
    if state.session_state == "LOST":
        return "LOST"
    if not state.connected:
        return "DISCONNECTED"
    if state.system_state == "FAULT":
        return "FAULT"
    if state.fault or state.error_latched or state.mode == "ERROR" or (
        state.last_error and state.last_error.upper() != "NONE"
    ):
        return "ERROR"
    if state.system_state in {"READY", "RUNNING", "IDLE"}:
        return state.system_state
    if state.mode == "PID" or state.heater_output_percent > 0:
        return "RUNNING"
    return "IDLE"
