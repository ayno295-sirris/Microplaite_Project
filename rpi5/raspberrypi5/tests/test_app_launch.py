from __future__ import annotations

import os
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from microplaite_ui import main as app_main

LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "launch_microplaite_ui.sh"


@dataclass
class _FakeApplication:
    exit_code: int = 0

    def exec(self) -> int:
        return self.exit_code


class _FakeWindow:
    def __init__(self, controller: object) -> None:
        self.controller = controller
        self.shown = False
        self.fullscreen = False

    def show(self) -> None:
        self.shown = True

    def showFullScreen(self) -> None:
        self.fullscreen = True


@pytest.fixture
def launch_fakes(monkeypatch: pytest.MonkeyPatch) -> tuple[list[_FakeWindow], object]:
    application = _FakeApplication(exit_code=17)
    windows: list[_FakeWindow] = []
    controller = object()

    monkeypatch.setattr(app_main, "QApplication", lambda _argv: application)
    monkeypatch.setattr(app_main, "_acquire_instance_lock", lambda: object())
    monkeypatch.setattr(app_main, "AppController", lambda _client: controller)
    monkeypatch.setattr(
        app_main,
        "MainWindow",
        lambda selected_controller: windows.append(_FakeWindow(selected_controller)) or windows[-1],
    )
    return windows, controller


def test_windowed_launch_shows_normal_window(
    launch_fakes: tuple[list[_FakeWindow], object],
) -> None:
    windows, controller = launch_fakes

    result = app_main.run_gui(client=object())

    assert result == 17
    assert len(windows) == 1
    assert windows[0].controller is controller
    assert windows[0].shown is True
    assert windows[0].fullscreen is False


def test_fullscreen_launch_shows_fullscreen_window(
    launch_fakes: tuple[list[_FakeWindow], object],
) -> None:
    windows, _controller = launch_fakes

    result = app_main.run_gui(client=object(), fullscreen=True)

    assert result == 17
    assert len(windows) == 1
    assert windows[0].shown is False
    assert windows[0].fullscreen is True


def test_second_instance_is_refused_before_controller_construction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    application = _FakeApplication()
    controller_constructed = False

    def unexpected_controller(_client: object) -> object:
        nonlocal controller_constructed
        controller_constructed = True
        return object()

    monkeypatch.setattr(app_main, "QApplication", lambda _argv: application)
    monkeypatch.setattr(app_main, "_acquire_instance_lock", lambda: None)
    monkeypatch.setattr(app_main, "AppController", unexpected_controller)

    result = app_main.run_gui(client=object())

    assert result == 2
    assert controller_constructed is False
    assert "already running" in capsys.readouterr().err.lower()


def _temporary_launcher_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    scripts = project / "scripts"
    python = project / ".venv" / "bin" / "python"
    scripts.mkdir(parents=True)
    python.parent.mkdir(parents=True)
    shutil.copy2(LAUNCHER, scripts / LAUNCHER.name)
    python.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'cwd=%s\\n\' "$PWD"\n'
        'printf \'args=%s\\n\' "$*"\n'
        'printf \'pythonpath=%s\\n\' "$PYTHONPATH"\n'
        "printf 'stdout-marker\\n'\n"
        "printf 'stderr-marker\\n' >&2\n"
        'exit "${FAKE_EXIT_CODE:-0}"\n',
        encoding="utf-8",
    )
    python.chmod(python.stat().st_mode | stat.S_IXUSR)
    return project


def _run_temporary_launcher(
    project: Path,
    *,
    home: Path,
    arguments: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update({"HOME": str(home), "FAKE_EXIT_CODE": "23"})
    return subprocess.run(
        [str(project / "scripts" / LAUNCHER.name), *arguments],
        cwd=home,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_manual_launcher_is_cwd_independent_and_keeps_terminal_output(
    tmp_path: Path,
) -> None:
    project = _temporary_launcher_project(tmp_path)
    home = tmp_path / "home"
    home.mkdir()

    result = _run_temporary_launcher(
        project,
        home=home,
        arguments=("--fullscreen",),
    )

    assert result.returncode == 23
    assert f"cwd={project}" in result.stdout
    assert f"args={project / 'scripts' / 'run_microplaite_ui.py'} --fullscreen" in result.stdout
    assert f"pythonpath={project / 'src'}" in result.stdout
    assert "stdout-marker" in result.stdout
    assert "stderr-marker" in result.stderr
    assert not (home / "MicroplaiteData" / "logs" / "autostart.log").exists()


def test_autostart_launcher_appends_output_and_propagates_exit_status(
    tmp_path: Path,
) -> None:
    project = _temporary_launcher_project(tmp_path)
    home = tmp_path / "home"
    home.mkdir()

    result = _run_temporary_launcher(
        project,
        home=home,
        arguments=("--autostart", "--fullscreen", "--port", "/dev/test-port"),
    )

    log_path = home / "MicroplaiteData" / "logs" / "autostart.log"
    assert result.returncode == 23
    assert result.stdout == ""
    assert result.stderr == ""
    assert log_path.exists()
    log = log_path.read_text(encoding="utf-8")
    assert "stdout-marker" in log
    assert "stderr-marker" in log
    assert "--autostart --fullscreen --port /dev/test-port" in log
