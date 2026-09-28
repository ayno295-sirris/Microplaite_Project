"""Validated JSON recipe definitions for V2 orchestration."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from microplaite_ui.config import THERMAL_TEST_MAX_TARGET_C

DEFAULT_RECIPE_DIRECTORY = Path.home() / "MicroplaiteData" / "recipes"
_DEFAULT_EXAMPLE = """{
  "name": "Test simple",
  "steps": [
    {"action": "SET_TEMPERATURE", "target_c": 44.3},
    {"action": "HEATER_PID_ON"},
    {
      "action": "WAIT_TEMPERATURE",
      "target_c": 44.3,
      "tolerance_c": 0.3,
      "timeout_s": 600
    },
    {"action": "PUMP_START", "rpm": 3.0},
    {"action": "WAIT", "seconds": 30},
    {"action": "PUMP_STOP"},
    {"action": "HEATER_OFF"}
  ]
}
"""

_ACTION_PARAMETERS: dict[RecipeAction, frozenset[str]]


class RecipeAction(StrEnum):
    SET_TEMPERATURE = "SET_TEMPERATURE"
    HEATER_PID_ON = "HEATER_PID_ON"
    HEATER_OFF = "HEATER_OFF"
    PUMP_START = "PUMP_START"
    PUMP_SET_RPM = "PUMP_SET_RPM"
    PUMP_STOP = "PUMP_STOP"
    PUMP_PRIME = "PUMP_PRIME"
    WAIT = "WAIT"
    WAIT_TEMPERATURE = "WAIT_TEMPERATURE"
    NEOPIXEL = "NEOPIXEL"


@dataclass(frozen=True, slots=True)
class RecipeStep:
    action: RecipeAction
    target_c: float | None = None
    tolerance_c: float | None = None
    timeout_s: float | None = None
    rpm: float | None = None
    seconds: float | None = None
    enabled: bool | None = None
    brightness: int | None = None


@dataclass(frozen=True, slots=True)
class RecipeDefinition:
    name: str
    steps: tuple[RecipeStep, ...]
    source: Path


class RecipeValidationError(ValueError):
    """Raised when a JSON recipe does not match the supported format."""


class RecipeStore:
    def __init__(self, directory: Path = DEFAULT_RECIPE_DIRECTORY) -> None:
        self.directory = Path(directory)

    def list_files(self) -> list[Path]:
        self.directory.mkdir(parents=True, exist_ok=True)
        example = self.directory / "test_simple.json"
        try:
            with example.open("x", encoding="utf-8") as stream:
                stream.write(_DEFAULT_EXAMPLE)
        except FileExistsError:
            pass
        return sorted(self.directory.glob("*.json"), key=lambda path: path.name)

    def load(self, path: Path) -> RecipeDefinition:
        source = Path(path)
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RecipeValidationError(f"{source.name}: invalid JSON") from exc

        if not isinstance(data, dict):
            self._raise(source, "recipe must be an object")
        unexpected = set(data) - {"name", "steps"}
        if unexpected:
            self._raise(source, f"unexpected fields: {', '.join(sorted(unexpected))}")

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            self._raise(source, "name must be a non-empty string")
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            self._raise(source, "steps must be a non-empty array")

        steps = tuple(
            self._load_step(source, index, item)
            for index, item in enumerate(raw_steps, start=1)
        )
        return RecipeDefinition(name=name.strip(), steps=steps, source=source)

    def _load_step(self, source: Path, index: int, data: Any) -> RecipeStep:
        prefix = f"step {index}"
        if not isinstance(data, dict):
            self._raise(source, f"{prefix} must be an object")
        raw_action = data.get("action")
        try:
            action = RecipeAction(raw_action)
        except (TypeError, ValueError):
            self._raise(source, f"{prefix}: unknown action {raw_action!r}")

        required = _ACTION_PARAMETERS[action]
        provided = set(data) - {"action"}
        missing = required - provided
        if missing:
            self._raise(source, f"{prefix}: missing {', '.join(sorted(missing))}")
        unexpected = provided - required
        if unexpected:
            self._raise(source, f"{prefix}: unexpected {', '.join(sorted(unexpected))}")

        target_c = self._optional_number(source, prefix, data, "target_c")
        tolerance_c = self._optional_number(source, prefix, data, "tolerance_c")
        timeout_s = self._optional_number(source, prefix, data, "timeout_s")
        rpm = self._optional_number(source, prefix, data, "rpm")
        seconds = self._optional_number(source, prefix, data, "seconds")

        if target_c is not None and not 0.0 <= target_c <= THERMAL_TEST_MAX_TARGET_C:
            self._raise(
                source,
                f"{prefix}: target_c must be between 0 and {THERMAL_TEST_MAX_TARGET_C:g}",
            )
        if tolerance_c is not None and tolerance_c < 0.0:
            self._raise(source, f"{prefix}: tolerance_c must be non-negative")
        if timeout_s is not None and timeout_s <= 0.0:
            self._raise(source, f"{prefix}: timeout_s must be positive")
        if rpm is not None and not 0.0 <= rpm <= 100.0:
            self._raise(source, f"{prefix}: rpm must be between 0 and 100")
        if seconds is not None and seconds < 0.0:
            self._raise(source, f"{prefix}: seconds must be non-negative")

        enabled = data.get("enabled")
        if "enabled" in data and not isinstance(enabled, bool):
            self._raise(source, f"{prefix}: enabled must be a boolean")
        brightness = data.get("brightness")
        if "brightness" in data:
            if isinstance(brightness, bool) or not isinstance(brightness, int):
                self._raise(source, f"{prefix}: brightness must be an integer")
            if not 0 <= brightness <= 100:
                self._raise(source, f"{prefix}: brightness must be between 0 and 100")

        return RecipeStep(
            action=action,
            target_c=target_c,
            tolerance_c=tolerance_c,
            timeout_s=timeout_s,
            rpm=rpm,
            seconds=seconds,
            enabled=enabled if isinstance(enabled, bool) else None,
            brightness=brightness if isinstance(brightness, int) else None,
        )

    @classmethod
    def _optional_number(
        cls,
        source: Path,
        prefix: str,
        data: dict[str, Any],
        field: str,
    ) -> float | None:
        if field not in data:
            return None
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            cls._raise(source, f"{prefix}: {field} must be a number")
        number = float(value)
        if not math.isfinite(number):
            cls._raise(source, f"{prefix}: {field} must be finite")
        return number

    @staticmethod
    def _raise(source: Path, detail: str) -> None:
        raise RecipeValidationError(f"{source.name}: {detail}")


_ACTION_PARAMETERS = {
    RecipeAction.SET_TEMPERATURE: frozenset({"target_c"}),
    RecipeAction.HEATER_PID_ON: frozenset(),
    RecipeAction.HEATER_OFF: frozenset(),
    RecipeAction.PUMP_START: frozenset({"rpm"}),
    RecipeAction.PUMP_SET_RPM: frozenset({"rpm"}),
    RecipeAction.PUMP_STOP: frozenset(),
    RecipeAction.PUMP_PRIME: frozenset(),
    RecipeAction.WAIT: frozenset({"seconds"}),
    RecipeAction.WAIT_TEMPERATURE: frozenset(
        {"target_c", "tolerance_c", "timeout_s"}
    ),
    RecipeAction.NEOPIXEL: frozenset({"enabled", "brightness"}),
}
