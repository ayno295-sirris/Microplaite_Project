from __future__ import annotations

import os
import tempfile
from pathlib import Path

DESKTOP_FILE_NAME = "microplaite-control.desktop"
PROJECT_DIR = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT_DIR / "scripts" / "launch_microplaite_ui.sh"
TEMPLATE = PROJECT_DIR / "deploy" / "microplaite-control-autostart.desktop.in"


def _desktop_exec_arg(value: str) -> str:
    if not any(character.isspace() or character in {'"', "\\"} for character in value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_entry() -> str:
    if not LAUNCHER.is_file():
        raise FileNotFoundError(f"Missing launcher: {LAUNCHER}")
    if not TEMPLATE.is_file():
        raise FileNotFoundError(f"Missing autostart template: {TEMPLATE}")
    template = TEMPLATE.read_text(encoding="utf-8")
    return template.replace("@LAUNCHER@", _desktop_exec_arg(str(LAUNCHER)))


def install(target: Path | None = None) -> Path:
    installed = target or Path.home() / ".config" / "autostart" / DESKTOP_FILE_NAME
    installed.parent.mkdir(parents=True, exist_ok=True)
    content = render_entry()
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=installed.parent,
            prefix=f".{DESKTOP_FILE_NAME}.",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        temporary_path.chmod(0o644)
        os.replace(temporary_path, installed)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return installed


def main() -> int:
    installed = install()
    print(f"Autostart entry: {installed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
