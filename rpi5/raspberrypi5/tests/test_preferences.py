import json

from microplaite_ui.services.preferences import PreferencesStore, UserPreferences


def test_preferences_store_saves_and_loads_json(tmp_path) -> None:
    path = tmp_path / "settings.json"
    store = PreferencesStore(path)

    store.save(
        UserPreferences(
            target_c=42.25,
            pump_target_rpm=9.8,
            neopixel_enabled=False,
            neopixel_brightness_percent=35,
            timelapse_storage_mode="external",
            timelapse_interval_value=3,
            timelapse_interval_unit="minutes",
            timelapse_brightness_percent=44,
            timelapse_light_duration_s=2.5,
            timelapse_total_duration_min=90,
            timelapse_infinite=True,
            live_record_video=True,
            video_storage_mode="external",
        )
    )

    raw = json.loads(path.read_text(encoding="utf-8"))
    loaded = store.load()

    assert raw["target_c"] == 42.25
    assert loaded.target_c == 42.25
    assert loaded.pump_target_rpm == 9.8
    assert loaded.neopixel_enabled is False
    assert loaded.timelapse_storage_mode == "external"
    assert loaded.timelapse_interval_unit == "minutes"
    assert loaded.timelapse_infinite is True
    assert loaded.live_record_video is True
    assert loaded.video_storage_mode == "external"


def test_preferences_store_validates_bad_values(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "target_c": 999,
                "pump_target_rpm": -10,
                "neopixel_brightness_percent": 500,
                "timelapse_storage_mode": "bad",
                "timelapse_interval_value": 0,
                "timelapse_interval_unit": "hours",
                "timelapse_light_duration_s": 99,
                "timelapse_total_duration_min": -1,
                "live_record_video": 1,
                "video_storage_mode": "bad",
            }
        ),
        encoding="utf-8",
    )

    prefs = PreferencesStore(path).load()

    assert prefs.target_c == 80.0
    assert prefs.pump_target_rpm == 0.0
    assert prefs.neopixel_brightness_percent == 100
    assert prefs.timelapse_storage_mode == "internal"
    assert prefs.timelapse_interval_value == 1
    assert prefs.timelapse_interval_unit == "seconds"
    assert prefs.timelapse_light_duration_s == 60.0
    assert prefs.timelapse_total_duration_min == 1
    assert prefs.live_record_video is True
    assert prefs.video_storage_mode == "internal"
