"""Shared storage paths and writability checks."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path


MIN_FREE_BYTES = 50 * 1024 * 1024
INTERNAL_TIMELAPSE_STORAGE = Path.home() / "Microplaite" / "timelapse"
INTERNAL_VIDEO_STORAGE = Path.home() / "Microplaite" / "video"


def resolve_storage_path(kind: str, mode: str) -> Path:
    if mode == "external":
        external = external_storage_path()
        if external is None:
            return Path("/media")
        return external / "Microplaite" / kind
    if kind == "video":
        return INTERNAL_VIDEO_STORAGE
    return INTERNAL_TIMELAPSE_STORAGE


def external_storage_path() -> Path | None:
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


def free_bytes(path: Path) -> int:
    try:
        target = path if path.exists() else path.parent
        while not target.exists() and target != target.parent:
            target = target.parent
        return shutil.disk_usage(target).free
    except OSError:
        return 0


def ensure_writable(path: Path) -> None:
    if str(path) == "/media":
        raise RuntimeError("External disk absent or not writable")
    path.mkdir(parents=True, exist_ok=True)
    if free_bytes(path) < MIN_FREE_BYTES:
        raise RuntimeError("disk space too low")
    probe = path / ".microplaite_write_test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)


def unique_path(base: Path, stem: str, suffix: str) -> Path:
    candidate = base / f"{stem}{suffix}"
    index = 2
    while candidate.exists():
        candidate = base / f"{stem}_{index}{suffix}"
        index += 1
    return candidate


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
