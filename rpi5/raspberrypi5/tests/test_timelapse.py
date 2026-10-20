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


def test_timelapse_default_stabilization_is_2500_ms() -> None:
    assert TimelapseSettings().light_duration_s == 2.5


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


def test_timelapse_rejects_interval_not_longer_than_stabilization(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(timelapse_module, "INTERNAL_STORAGE", tmp_path)
    fake = FakeHardware()
    service = service_for(fake, [])

    ok = service.start(TimelapseSettings(interval_s=2.5, light_duration_s=2.5))

    assert ok is False
    assert "stabilization" in service.snapshot().error.lower()
    assert not list(tmp_path.glob("timelapse_*"))


def test_timelapse_uses_nominal_capture_deadlines_without_cumulative_drift(
    tmp_path,
) -> None:
    now = [0.0]
    events: list[tuple[str, float]] = []

    def clock() -> float:
        return now[0]

    def capture(destination: Path) -> Path:
        destination.write_bytes(b"fake-jpeg")
        events.append(("capture", clock()))
        if len([event for event, _at in events if event == "capture"]) == 3:
            service._stop_event.set()
        return destination

    service = TimelapseService(
        capture,
        lambda: events.append(("on", clock())),
        lambda: events.append(("off", clock())),
        lambda _percent: None,
        clock=clock,
    )

    def wait_until(deadline: float) -> bool:
        now[0] = deadline
        return not service._stop_event.is_set()

    service._wait_until = wait_until
    service._set_snapshot(running=True)
    service._run_timelapse(
        TimelapseSettings(interval_s=10.0, light_duration_s=2.5, infinite=True),
        tmp_path,
    )

    assert [at for event, at in events if event == "on"] == [7.5, 17.5, 27.5]
    assert [at for event, at in events if event == "capture"] == [10.0, 20.0, 30.0]


def test_timelapse_cancellation_during_stabilization_does_not_capture_and_turns_off(
    tmp_path,
) -> None:
    fake = FakeHardware()
    service = service_for(fake, [])

    def cancel_wait(_deadline: float) -> bool:
        service._stop_event.set()
        return False

    service._wait_until = cancel_wait
    saved = service._capture_once(
        TimelapseSettings(light_duration_s=2.5),
        tmp_path / "cancelled.jpg",
        for_test=False,
        capture_deadline=10.0,
    )

    assert saved is None
    assert not (tmp_path / "cancelled.jpg").exists()
    assert fake.events[-1] == "off"


def test_timelapse_skips_missed_slot_instead_of_starting_concurrent_capture(
    tmp_path,
) -> None:
    now = [0.0]
    captures: list[float] = []
    logs: list[str] = []

    def clock() -> float:
        return now[0]

    def capture(destination: Path) -> Path:
        destination.write_bytes(b"fake-jpeg")
        captures.append(clock())
        if len(captures) == 1:
            now[0] = 19.0
        else:
            service._stop_event.set()
        return destination

    service = TimelapseService(
        capture,
        lambda: None,
        lambda: None,
        lambda _percent: None,
        logs.append,
        clock=clock,
    )

    def wait_until(deadline: float) -> bool:
        now[0] = deadline
        return not service._stop_event.is_set()

    service._wait_until = wait_until
    service._set_snapshot(running=True)
    service._run_timelapse(
        TimelapseSettings(interval_s=10.0, light_duration_s=2.5, infinite=True),
        tmp_path,
    )

    assert captures == [10.0, 30.0]
    assert logs.count("capture skipped because previous capture is still running") == 1


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
