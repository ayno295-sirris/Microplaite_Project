from __future__ import annotations

import json
from pathlib import Path

import pytest

from microplaite_ui.config import THERMAL_TEST_MAX_TARGET_C
from microplaite_ui.services.recipes import RecipeStore, RecipeValidationError


def test_loads_valid_recipe_with_all_supported_actions(tmp_path: Path) -> None:
    path = tmp_path / "all-actions.json"
    path.write_text(
        json.dumps(
            {
                "name": "All actions",
                "steps": [
                    {"action": "SET_TEMPERATURE", "target_c": 44.3},
                    {"action": "HEATER_PID_ON"},
                    {"action": "HEATER_OFF"},
                    {"action": "PUMP_START", "rpm": 3.0},
                    {"action": "PUMP_SET_RPM", "rpm": 4.0},
                    {"action": "PUMP_STOP"},
                    {"action": "PUMP_PRIME"},
                    {"action": "WAIT", "seconds": 0.5},
                    {
                        "action": "WAIT_TEMPERATURE",
                        "target_c": 44.3,
                        "tolerance_c": 0.3,
                        "timeout_s": 600,
                    },
                    {"action": "NEOPIXEL", "enabled": True, "brightness": 35},
                ],
            }
        ),
        encoding="utf-8",
    )

    recipe = RecipeStore(tmp_path).load(path)

    assert recipe.name == "All actions"
    assert tuple(step.action.value for step in recipe.steps) == (
        "SET_TEMPERATURE",
        "HEATER_PID_ON",
        "HEATER_OFF",
        "PUMP_START",
        "PUMP_SET_RPM",
        "PUMP_STOP",
        "PUMP_PRIME",
        "WAIT",
        "WAIT_TEMPERATURE",
        "NEOPIXEL",
    )
    assert recipe.steps[0].target_c == 44.3
    assert recipe.steps[-1].enabled is True
    assert recipe.steps[-1].brightness == 35


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        ([], "must be an object"),
        ({"name": "", "steps": [{"action": "PUMP_STOP"}]}, "name must be"),
        ({"name": "Empty", "steps": []}, "steps must be"),
        (
            {"name": "Bad", "steps": [{"action": "UNKNOWN"}]},
            "unknown action",
        ),
        (
            {"name": "Bad", "steps": [{"action": "PUMP_START"}]},
            "missing",
        ),
        (
            {
                "name": "Bad",
                "steps": [{"action": "PUMP_STOP", "rpm": 3.0}],
            },
            "unexpected",
        ),
        (
            {
                "name": "Bad",
                "steps": [{"action": "SET_TEMPERATURE", "target_c": True}],
            },
            "must be",
        ),
        (
            {
                "name": "Bad",
                "steps": [{"action": "PUMP_START", "rpm": float("inf")}],
            },
            "must be",
        ),
        (
            {
                "name": "Bad",
                "steps": [
                    {
                        "action": "SET_TEMPERATURE",
                        "target_c": THERMAL_TEST_MAX_TARGET_C + 0.1,
                    }
                ],
            },
            "must be",
        ),
        (
            {"name": "Bad", "steps": [{"action": "PUMP_START", "rpm": 100.1}]},
            "must be",
        ),
        (
            {"name": "Bad", "steps": [{"action": "WAIT", "seconds": -0.1}]},
            "must be",
        ),
        (
            {
                "name": "Bad",
                "steps": [
                    {
                        "action": "WAIT_TEMPERATURE",
                        "target_c": 44.3,
                        "tolerance_c": 0.3,
                        "timeout_s": 0,
                    }
                ],
            },
            "must be",
        ),
        (
            {
                "name": "Bad",
                "steps": [
                    {
                        "action": "WAIT_TEMPERATURE",
                        "target_c": 44.3,
                        "tolerance_c": -0.1,
                        "timeout_s": 10,
                    }
                ],
            },
            "must be",
        ),
        (
            {
                "name": "Bad",
                "steps": [
                    {"action": "NEOPIXEL", "enabled": 1, "brightness": 35}
                ],
            },
            "must be",
        ),
        (
            {
                "name": "Bad",
                "steps": [
                    {"action": "NEOPIXEL", "enabled": True, "brightness": 35.5}
                ],
            },
            "must be",
        ),
        (
            {
                "name": "Bad",
                "steps": [
                    {"action": "NEOPIXEL", "enabled": True, "brightness": 101}
                ],
            },
            "must be",
        ),
    ],
)
def test_rejects_invalid_recipe_data(
    tmp_path: Path, data: object, fragment: str
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(RecipeValidationError, match=fragment):
        RecipeStore(tmp_path).load(path)


def test_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(RecipeValidationError, match="invalid JSON"):
        RecipeStore(tmp_path).load(path)


def test_list_files_creates_directory_and_default_example(tmp_path: Path) -> None:
    directory = tmp_path / "recipes"
    store = RecipeStore(directory)

    files = store.list_files()

    assert [path.name for path in files] == ["test_simple.json"]
    assert store.load(files[0]).name == "Test simple"


def test_list_files_never_overwrites_existing_example(tmp_path: Path) -> None:
    directory = tmp_path / "recipes"
    directory.mkdir()
    example = directory / "test_simple.json"
    original = '{"name":"User recipe","steps":[{"action":"WAIT","seconds":1}]}'
    example.write_text(original, encoding="utf-8")

    RecipeStore(directory).list_files()

    assert example.read_text(encoding="utf-8") == original


def test_malformed_file_does_not_hide_other_recipe_paths(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    (tmp_path / "good.json").write_text(
        '{"name":"Good","steps":[{"action":"WAIT","seconds":1}]}',
        encoding="utf-8",
    )

    files = RecipeStore(tmp_path).list_files()

    assert [path.name for path in files] == [
        "bad.json",
        "good.json",
        "test_simple.json",
    ]
    with pytest.raises(RecipeValidationError):
        RecipeStore(tmp_path).load(tmp_path / "bad.json")
