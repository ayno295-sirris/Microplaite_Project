from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess


APP_NAME = "Microplaite Control"
DESKTOP_FILE_NAME = "microplaite-control.desktop"
PROJECT_DIR = Path(__file__).resolve().parents[1]
LAUNCH_SCRIPT = PROJECT_DIR / "scripts" / "launch_microplaite_ui.sh"


def main() -> int:
    if not LAUNCH_SCRIPT.exists():
        raise SystemExit(f"Missing launcher: {LAUNCH_SCRIPT}")

    _make_executable(LAUNCH_SCRIPT)
    content = _desktop_entry()

    app_shortcut = Path.home() / ".local" / "share" / "applications" / DESKTOP_FILE_NAME
    desktop_shortcut = _desktop_dir() / f"{APP_NAME}.desktop"

    _write_shortcut(app_shortcut, content)
    _write_shortcut(desktop_shortcut, content)

    print(f"Application menu shortcut: {app_shortcut}")
    print(f"Desktop shortcut: {desktop_shortcut}")
    return 0


def _desktop_entry() -> str:
    return "\n".join(
        (
            "[Desktop Entry]",
            "Type=Application",
            f"Name={APP_NAME}",
            "Comment=Launch the Microplaite Raspberry Pi GUI",
            f"Exec={_desktop_exec_arg(str(LAUNCH_SCRIPT))}",
            f"Path={PROJECT_DIR}",
            "Icon=applications-science",
            "Terminal=false",
            "StartupNotify=true",
            "Categories=Science;Utility;",
            "",
        )
    )


def _desktop_exec_arg(value: str) -> str:
    if not any(char.isspace() or char in {'"', "\\"} for char in value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _desktop_dir() -> Path:
    configured = _xdg_desktop_dir()
    if configured:
        return configured
    for name in ("Desktop", "Bureau"):
        candidate = Path.home() / name
        if candidate.exists():
            return candidate
    return Path.home() / "Desktop"


def _xdg_desktop_dir() -> Path | None:
    user_dirs = Path.home() / ".config" / "user-dirs.dirs"
    if not user_dirs.exists():
        return None
    for line in user_dirs.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("XDG_DESKTOP_DIR="):
            continue
        raw_value = line.split("=", 1)[1].strip().strip('"')
        raw_value = raw_value.replace("$HOME", str(Path.home()))
        return Path(os.path.expandvars(raw_value)).expanduser()
    return None


def _write_shortcut(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _make_executable(path)
    _mark_trusted(path)


def _make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _mark_trusted(path: Path) -> None:
    if shutil.which("gio") is None:
        return
    subprocess.run(
        ["gio", "set", str(path), "metadata::trusted", "true"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    raise SystemExit(main())
