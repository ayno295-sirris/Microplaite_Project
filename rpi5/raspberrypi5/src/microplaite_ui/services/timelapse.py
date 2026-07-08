"""Threaded timelapse service with guarded captures and session metadata."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable


MIN_FREE_BYTES = 50 * 1024 * 1024
INTERNAL_STORAGE = Path.home() / "Microplaite" / "timelapse"


@dataclass(slots=True)
class TimelapseSettings:
    storage_mode: str = "internal"
    interval_s: float = 10.0
    brightness_percent: int = 80
    light_duration_s: float = 1.0
    total_duration_s: float = 60.0
    infinite: bool = False


@dataclass(slots=True)
class TimelapseSnapshot:
    status: str = "stopped"
    running: bool = False
    live_running: bool = False
    capture_in_progress: bool = False
    frames_captured: int = 0
    last_file: str = ""
    session_dir: str = ""
    storage_path: str = str(INTERNAL_STORAGE)
    disk_free_bytes: int = 0
    error: str = ""
    estimated_frames: int = 0
    estimated_bytes: int = 0
    external_available: bool = False


@dataclass(slots=True)
class _Metadata:
    start: str
    end: str | None
    interval_s: float
    total_duration_s: float | None
    infinite: bool
    brightness_percent: int
    light_duration_s: float
    frames_captured: int
    storage_dir: str
    disk_free_bytes_start: int
    errors: list[str] = field(default_factory=list)


class TimelapseService:
    def __init__(
        self,
        capture_image: Callable[[Path], Path],
        neopixel_on: Callable[[], None],
        neopixel_off: Callable[[], None],
        set_neopixel_brightness: Callable[[int], None],
        log: Callable[[str], None] | None = None,
    ) -> None:
        self._capture_image = capture_image
        self._neopixel_on = neopixel_on
        self._neopixel_off = neopixel_off
        self._set_neopixel_brightness = set_neopixel_brightness
        self._log = log or (lambda message: None)
        self._lock = threading.Lock()
        self._capture_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot = TimelapseSnapshot()
        self._metadata: _Metadata | None = None
        self._settings = TimelapseSettings()

    def snapshot(self, settings: TimelapseSettings | None = None) -> TimelapseSnapshot:
        with self._lock:
            snap = TimelapseSnapshot(**asdict(self._snapshot))
        if settings is not None:
            path = self.resolve_storage_path(settings.storage_mode)
            snap.storage_path = str(path)
            snap.external_available = self.external_storage_path() is not None
            snap.disk_free_bytes = self.free_bytes(path)
            snap.estimated_frames = self.estimate_frames(settings)
            snap.estimated_bytes = snap.estimated_frames * 2_000_000
        return snap

    def set_live_running(self, running: bool) -> None:
        with self._lock:
            timelapse_running = self._snapshot.running
        if timelapse_running:
            status = "timelapse running"
        else:
            status = "live video active" if running else "stopped"
        self._set_snapshot(live_running=running, status=status)

    def start(self, settings: TimelapseSettings) -> bool:
        settings = self._validated(settings)
        with self._lock:
            if self._snapshot.running:
                self._append_log("timelapse already running")
                return False
        try:
            session_dir = self._create_session(settings)
        except Exception as exc:
            self._set_error(str(exc))
            return False
        self._settings = settings
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_timelapse,
            args=(settings, session_dir),
            name="MicroplaiteTimelapse",
            daemon=True,
        )
        self._set_snapshot(
            status="timelapse running",
            running=True,
            error="",
            frames_captured=0,
            last_file="",
            session_dir=str(session_dir),
            storage_path=str(session_dir.parent),
            disk_free_bytes=self.free_bytes(session_dir),
        )
        self._thread.start()
        self._append_log(f"timelapse started in {session_dir}")
        return True

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._safe_neopixel_off()
        self._finish_metadata()
        self._set_snapshot(running=False, capture_in_progress=False, status="stopped")
        self._append_log("timelapse stopped")

    def test_capture(self, settings: TimelapseSettings) -> bool:
        settings = self._validated(settings)
        with self._lock:
            if self._snapshot.running:
                self._append_log("test capture refused because timelapse is running")
                return False
        path = self.resolve_storage_path(settings.storage_mode)
        try:
            self._ensure_writable(path)
            filename = f"test_capture_{_stamp()}.jpg"
            self._capture_once(settings, path / filename, for_test=True)
            return True
        except Exception as exc:
            self._set_error(str(exc))
            return False

    def estimate_frames(self, settings: TimelapseSettings) -> int:
        if settings.infinite:
            return 0
        interval = max(1.0, float(settings.interval_s))
        return max(1, int(float(settings.total_duration_s) // interval))

    def resolve_storage_path(self, mode: str) -> Path:
        if mode == "external":
            external = self.external_storage_path()
            if external is None:
                return Path("/media")
            return external / "Microplaite" / "timelapse"
        return INTERNAL_STORAGE

    def external_storage_path(self) -> Path | None:
        candidates: list[Path] = []
        for root in (Path("/media") / os.environ.get("USER", ""), Path("/media"), Path("/mnt")):
            if not root.exists():
                continue
            try:
                for child in root.iterdir():
                    if child.is_dir() and os.access(child, os.W_OK):
                        candidates.append(child)
            except OSError:
                continue
        return candidates[0] if candidates else None

    def free_bytes(self, path: Path) -> int:
        try:
            target = path if path.exists() else path.parent
            while not target.exists() and target != target.parent:
                target = target.parent
            return shutil.disk_usage(target).free
        except OSError:
            return 0

    def _run_timelapse(self, settings: TimelapseSettings, session_dir: Path) -> None:
        started = time.monotonic()
        next_start = started + settings.interval_s
        image_index = 1
        try:
            while not self._stop_event.is_set():
                if not settings.infinite and time.monotonic() - started >= settings.total_duration_s:
                    break
                wait_s = max(0.0, next_start - time.monotonic())
                if self._stop_event.wait(wait_s):
                    break
                if self.free_bytes(session_dir) < MIN_FREE_BYTES:
                    raise RuntimeError("disk space too low, timelapse stopped")
                filename = f"img_{image_index:06d}_{_stamp()}.jpg"
                capture_started = time.monotonic()
                self._capture_once(settings, session_dir / filename, for_test=False)
                image_index += 1
                elapsed = time.monotonic() - capture_started
                if elapsed > settings.interval_s:
                    self._append_log("capture skipped because previous capture is still running")
                while next_start <= time.monotonic():
                    next_start += settings.interval_s
        except Exception as exc:
            self._set_error(str(exc))
            self._record_error(str(exc))
        finally:
            self._safe_neopixel_off()
            self._finish_metadata()
            status = "error" if self.snapshot().error else "stopped"
            self._set_snapshot(running=False, capture_in_progress=False, status=status)

    def _capture_once(self, settings: TimelapseSettings, destination: Path, for_test: bool) -> Path:
        if not self._capture_lock.acquire(blocking=False):
            self._append_log("capture skipped because previous capture is still running")
            return destination
        self._set_snapshot(capture_in_progress=True, status="capture in progress", error="")
        try:
            self._set_neopixel_brightness(settings.brightness_percent)
            self._neopixel_on()
            self._sleep_light(settings.light_duration_s)
            saved = self._capture_image(destination)
            frames = self._snapshot.frames_captured + (0 if for_test else 1)
            self._set_snapshot(
                frames_captured=frames,
                last_file=str(saved),
                disk_free_bytes=self.free_bytes(saved.parent),
                status="timelapse running" if not for_test else "stopped",
            )
            self._update_metadata(frames)
            self._append_log(f"capture saved: {saved}")
            return saved
        finally:
            self._safe_neopixel_off()
            self._set_snapshot(capture_in_progress=False)
            self._capture_lock.release()

    def _sleep_light(self, seconds: float) -> None:
        end = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < end:
            if self._stop_event.wait(min(0.05, end - time.monotonic())):
                break

    def _create_session(self, settings: TimelapseSettings) -> Path:
        base = self.resolve_storage_path(settings.storage_mode)
        self._ensure_writable(base)
        session_dir = _unique_dir(base, f"timelapse_{_stamp()}")
        session_dir.mkdir(parents=True, exist_ok=False)
        free = self.free_bytes(session_dir)
        self._metadata = _Metadata(
            start=datetime.now().isoformat(timespec="seconds"),
            end=None,
            interval_s=settings.interval_s,
            total_duration_s=None if settings.infinite else settings.total_duration_s,
            infinite=settings.infinite,
            brightness_percent=settings.brightness_percent,
            light_duration_s=settings.light_duration_s,
            frames_captured=0,
            storage_dir=str(session_dir),
            disk_free_bytes_start=free,
        )
        self._write_metadata(session_dir)
        return session_dir

    def _ensure_writable(self, path: Path) -> None:
        if str(path) == "/media":
            raise RuntimeError("external disk absent or not writable")
        path.mkdir(parents=True, exist_ok=True)
        if self.free_bytes(path) < MIN_FREE_BYTES:
            raise RuntimeError("disk space too low")
        probe = path / ".microplaite_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)

    def _validated(self, settings: TimelapseSettings) -> TimelapseSettings:
        return TimelapseSettings(
            storage_mode=settings.storage_mode if settings.storage_mode in {"internal", "external"} else "internal",
            interval_s=max(1.0, float(settings.interval_s)),
            brightness_percent=max(0, min(100, int(settings.brightness_percent))),
            light_duration_s=max(0.0, float(settings.light_duration_s)),
            total_duration_s=max(1.0, float(settings.total_duration_s)),
            infinite=bool(settings.infinite),
        )

    def _safe_neopixel_off(self) -> None:
        try:
            self._neopixel_off()
        except Exception as exc:
            self._record_error(f"NeoPixel OFF failed: {exc}")

    def _set_error(self, message: str) -> None:
        self._record_error(message)
        self._set_snapshot(status="error", running=False, capture_in_progress=False, error=message)
        self._append_log(f"timelapse error: {message}")

    def _record_error(self, message: str) -> None:
        if self._metadata is not None:
            self._metadata.errors.append(message)

    def _update_metadata(self, frames: int) -> None:
        if self._metadata is None:
            return
        self._metadata.frames_captured = frames
        self._write_metadata(Path(self._metadata.storage_dir))

    def _finish_metadata(self) -> None:
        if self._metadata is None:
            return
        self._metadata.end = datetime.now().isoformat(timespec="seconds")
        self._write_metadata(Path(self._metadata.storage_dir))

    def _write_metadata(self, session_dir: Path) -> None:
        if self._metadata is None:
            return
        try:
            (session_dir / "metadata.json").write_text(
                json.dumps(asdict(self._metadata), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self._append_log(f"metadata write failed: {exc}")

    def _set_snapshot(self, **updates: object) -> None:
        with self._lock:
            for key, value in updates.items():
                setattr(self._snapshot, key, value)

    def _append_log(self, message: str) -> None:
        self._log(message)


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _unique_dir(base: Path, name: str) -> Path:
    candidate = base / name
    index = 2
    while candidate.exists():
        candidate = base / f"{name}_{index}"
        index += 1
    return candidate
