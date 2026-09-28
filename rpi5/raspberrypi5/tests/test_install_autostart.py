from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[1]
INSTALLER = PROJECT_DIR / "scripts" / "install_autostart.py"
LAUNCHER = PROJECT_DIR / "scripts" / "launch_microplaite_ui.sh"
DESKTOP_FILE_NAME = "microplaite-control.desktop"


def _install(home: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    return subprocess.run(
        [str(PROJECT_DIR / ".venv" / "bin" / "python"), str(INSTALLER)],
        cwd=home,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_installer_creates_valid_xdg_autostart_entry(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    result = _install(home)

    installed = home / ".config" / "autostart" / DESKTOP_FILE_NAME
    assert result.returncode == 0, result.stderr
    assert installed.exists()
    content = installed.read_text(encoding="utf-8")
    assert f"Exec={LAUNCHER} --autostart --fullscreen" in content
    assert "Terminal=false" in content
    assert "Path=" not in content
    assert str(installed) in result.stdout

    validator = shutil.which("desktop-file-validate")
    if validator is None:
        pytest.skip("desktop-file-validate is not installed")
    validation = subprocess.run(
        [validator, str(installed)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert validation.returncode == 0, validation.stderr


def test_reinstall_updates_the_same_autostart_entry(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    installed = home / ".config" / "autostart" / DESKTOP_FILE_NAME

    first = _install(home)
    installed.write_text("obsolete\n", encoding="utf-8")
    second = _install(home)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "obsolete" not in installed.read_text(encoding="utf-8")
    assert [path.name for path in installed.parent.glob("*.desktop")] == [
        DESKTOP_FILE_NAME
    ]
