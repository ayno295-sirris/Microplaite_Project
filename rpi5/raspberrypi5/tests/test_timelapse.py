import json
import time
from pathlib import Path

from microplaite_ui.services import timelapse as timelapse_module
from microplaite_ui.services.timelapse import TimelapseService, TimelapseSettings


class FakeHardware:
    def __init__(self) -> None:
        self.events: list[str] = []

    def capture(self, destination: Path) -> Path:
        destination.write_bytes(b"fake-jpeg")
        self.events.append(f"capture:{destination.name}")
        return destination

    def on(self) -> None:
        self.events.append("on")

    def off(self) -> None:
        self.events.append("off")

    def brightness(self, percent: int) -> None:
        self.events.append(f"brightness:{percent}")


def service_for(fake: FakeHardware, logs: list[str]) -> TimelapseService:
    return TimelapseService(fake.capture, fake.on, fake.off, fake.brightness, logs.append)


def test_test_capture_turns_neopixel_off_and_saves_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(timelapse_module, "INTERNAL_STORAGE", tmp_path)
    fake = FakeHardware()
    logs: list[str] = []
    service = service_for(fake, logs)

    ok = service.test_capture(
        TimelapseSettings(interval_s=1, brightness_percent=35, light_duration_s=0)
    )

    assert ok is True
    assert fake.events[:3] == ["brightness:35", "on", "capture:" + next(tmp_path.glob("test_capture_*.jpg")).name]
    assert fake.events[-1] == "off"
    assert service.snapshot().last_file.endswith(".jpg")
    assert any("capture saved" in line for line in logs)


def test_test_capture_turns_neopixel_off_after_camera_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(timelapse_module, "INTERNAL_STORAGE", tmp_path)
    fake = FakeHardware()

    def broken_capture(destination: Path) -> Path:
        raise RuntimeError("camera failed")

    service = TimelapseService(broken_capture, fake.on, fake.off, fake.brightness)

    ok = service.test_capture(TimelapseSettings(light_duration_s=0))

    assert ok is False
    assert fake.events[-1] == "off"
    assert service.snapshot().status == "error"
    assert "camera failed" in service.snapshot().error


def test_timelapse_session_writes_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(timelapse_module, "INTERNAL_STORAGE", tmp_path)
    fake = FakeHardware()
    service = service_for(fake, [])

    ok = service.start(TimelapseSettings(interval_s=1, total_duration_s=2, light_duration_s=0))
    assert ok is True
    time.sleep(1.25)
    service.stop()

    sessions = list(tmp_path.glob("timelapse_*"))
    assert len(sessions) == 1
    metadata = json.loads((sessions[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["frames_captured"] >= 1
    assert metadata["interval_s"] == 1.0
    assert metadata["end"] is not None
    assert list(sessions[0].glob("img_*.jpg"))


def test_timelapse_start_refuses_when_live_video_is_running(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(timelapse_module, "INTERNAL_STORAGE", tmp_path)
    fake = FakeHardware()
    logs: list[str] = []
    service = service_for(fake, logs)

    assert service.set_live_running(True) is True
    ok = service.start(TimelapseSettings(interval_s=1, light_duration_s=0))

    assert ok is False
    snap = service.snapshot()
    assert snap.running is False
    assert snap.live_running is True
    assert "Stop live video before starting timelapse" in snap.error
    assert logs[-1] == "Stop live video before starting timelapse"
    assert not list(tmp_path.glob("timelapse_*"))


def test_live_video_refuses_when_timelapse_is_running(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(timelapse_module, "INTERNAL_STORAGE", tmp_path)
    fake = FakeHardware()
    logs: list[str] = []
    service = service_for(fake, logs)

    assert service.start(TimelapseSettings(interval_s=60, total_duration_s=60, light_duration_s=0)) is True
    try:
        ok = service.set_live_running(True)

        assert ok is False
        snap = service.snapshot()
        assert snap.running is True
        assert snap.live_running is False
        assert snap.status == "timelapse running"
        assert "Stop timelapse before starting live video" in logs
    finally:
        service.stop()


def test_test_capture_refuses_when_timelapse_is_running(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(timelapse_module, "INTERNAL_STORAGE", tmp_path)
    fake = FakeHardware()
    logs: list[str] = []
    service = service_for(fake, logs)

    assert service.start(TimelapseSettings(interval_s=60, total_duration_s=60, light_duration_s=0)) is True
    try:
        ok = service.test_capture(TimelapseSettings(light_duration_s=0))

        assert ok is False
        assert any("test capture refused because timelapse is running" in line for line in logs)
        assert not list(tmp_path.glob("test_capture_*.jpg"))
    finally:
        service.stop()


def test_test_capture_refuses_when_live_video_is_running(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(timelapse_module, "INTERNAL_STORAGE", tmp_path)
    fake = FakeHardware()
    logs: list[str] = []
    service = service_for(fake, logs)

    assert service.set_live_running(True) is True
    ok = service.test_capture(TimelapseSettings(light_duration_s=0))

    assert ok is False
    assert any("test capture refused because live video is running" in line for line in logs)
    assert fake.events == []
    assert not list(tmp_path.glob("test_capture_*.jpg"))
