"""Persistent user preferences for the Raspberry Pi UI."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from microplaite_ui.config import APP_NAME, DEFAULT_TARGET_C


PREFERENCES_PATH_ENV = "MICROPLAITE_PREFERENCES_PATH"


@dataclass(slots=True)
class UserPreferences:
    target_c: float = DEFAULT_TARGET_C
    pump_target_rpm: float = 50.0
    neopixel_enabled: bool = True
    neopixel_brightness_percent: int = 80
    timelapse_storage_mode: str = "internal"
    timelapse_interval_value: int = 10
    timelapse_interval_unit: str = "seconds"
    timelapse_brightness_percent: int = 80
    timelapse_light_duration_s: float = 1.0
    timelapse_total_duration_min: int = 60
    timelapse_infinite: bool = False
    live_record_video: bool = False
    video_storage_mode: str = "internal"


class PreferencesStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_preferences_path()

    def load(self) -> UserPreferences:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return UserPreferences()
        if not isinstance(raw, dict):
            return UserPreferences()
        return _validated(raw)

    def save(self, preferences: UserPreferences) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(asdict(preferences), indent=2), encoding="utf-8")
        temp.replace(self.path)


def default_preferences_path() -> Path:
    override = os.getenv(PREFERENCES_PATH_ENV)
    if override:
        return Path(override)
    root = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / APP_NAME / "preferences.json"


def _validated(raw: dict[str, Any]) -> UserPreferences:
    names = {field.name for field in fields(UserPreferences)}
    values = {key: raw[key] for key in names if key in raw}
    prefs = UserPreferences(**values)
    prefs.target_c = _clamp_float(prefs.target_c, 0.0, 80.0, DEFAULT_TARGET_C, 2)
    prefs.pump_target_rpm = _clamp_float(prefs.pump_target_rpm, 0.0, 100.0, 50.0, 1)
    prefs.neopixel_enabled = bool(prefs.neopixel_enabled)
    prefs.neopixel_brightness_percent = _clamp_int(prefs.neopixel_brightness_percent, 0, 100, 80)
    prefs.timelapse_storage_mode = prefs.timelapse_storage_mode if prefs.timelapse_storage_mode in {"internal", "external"} else "internal"
    prefs.timelapse_interval_value = _clamp_int(prefs.timelapse_interval_value, 1, 86400, 10)
    prefs.timelapse_interval_unit = prefs.timelapse_interval_unit if prefs.timelapse_interval_unit in {"seconds", "minutes"} else "seconds"
    prefs.timelapse_brightness_percent = _clamp_int(prefs.timelapse_brightness_percent, 0, 100, 80)
    prefs.timelapse_light_duration_s = _clamp_float(prefs.timelapse_light_duration_s, 0.0, 60.0, 1.0, 1)
    prefs.timelapse_total_duration_min = _clamp_int(prefs.timelapse_total_duration_min, 1, 10080, 60)
    prefs.timelapse_infinite = bool(prefs.timelapse_infinite)
    prefs.live_record_video = bool(prefs.live_record_video)
    prefs.video_storage_mode = prefs.video_storage_mode if prefs.video_storage_mode in {"internal", "external"} else "internal"
    return prefs


def _clamp_float(value: object, low: float, high: float, default: float, digits: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(low, min(high, number)), digits)


def _clamp_int(value: object, low: int, high: int, default: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = default
    return max(low, min(high, number))
