# Raspberry Pi Application Autostart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Start the existing Microplaite UI automatically after the Raspberry Pi graphical session opens, in full screen, while preserving manual launch behavior and refusing concurrent instances.

**Architecture:** The existing production shell launcher remains the only launch path. A small XDG autostart installer renders one `.desktop` entry that invokes this launcher with `--autostart --fullscreen`. The Python entry point controls full-screen presentation and owns a process-lifetime `QLockFile`; the shell launcher only adds append-only startup diagnostics for autostart launches. Existing V2 connection failure handling keeps the UI open in `DISCONNECTED` without retries.

**Tech Stack:** Bash, Python 3.11+, PySide6 (`QLockFile`, `QStandardPaths`), XDG `.desktop`, pytest, Ruff.

## Global Constraints

- Start from commit `763967408b47d369a6f69d811673731279ac4268` on `software-v2/autostart-rpi-001`.
- Raspberry Pi implementation remains inside `rpi5/raspberrypi5/`.
- Do not modify ESP32 firmware, V2 protocol, recipes, CSV logging, camera, supervision, or networking.
- Do not add automatic serial reconnect, application restart, watchdog, systemd service, or a second launcher.
- The manual launcher without `--fullscreen` keeps its current windowed behavior.
- The application must stay usable in `DISCONNECTED` when opening the serial port fails.
- The installed desktop entry must not depend on the caller's current directory.
- Preserve the existing untracked file under `docs/superpowers/specs/` exactly.
- Do not reboot the Raspberry Pi.
- The final commit message is exactly `Add Raspberry Pi application autostart`.

---

### Task 1: Full-screen option and single-instance ownership

**Files:**
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/main.py`
- Modify: `rpi5/raspberrypi5/scripts/run_microplaite_ui.py`
- Create: `rpi5/raspberrypi5/tests/test_app_launch.py`

- [ ] Write failing tests proving that windowed launch calls `show()`, full-screen launch calls `showFullScreen()`, and failure to acquire the application lock returns without constructing the controller/window.
- [ ] Add a small lock helper using `QLockFile` in `QStandardPaths.RuntimeLocation`, with a safe per-user fallback directory when Qt exposes no runtime location.
- [ ] Hold the lock object for the entire Qt event-loop lifetime and produce a clear diagnostic when a second instance is refused.
- [ ] Extend `run_gui(..., fullscreen=False)` and select `showFullScreen()` only when requested.
- [ ] Add `--fullscreen` and `--autostart` to the existing CLI; `--autostart` is accepted as launch context and does not alter UI behavior itself.
- [ ] Run the new targeted tests and confirm they pass.

### Task 2: Startup logging in the unique production launcher

**Files:**
- Modify: `rpi5/raspberrypi5/scripts/launch_microplaite_ui.sh`
- Create or extend: `rpi5/raspberrypi5/tests/test_app_launch.py`

- [ ] Write failing subprocess tests showing that the launcher resolves its project path independently of the caller's working directory and recognizes `--autostart`.
- [ ] Keep the current interpreter and `PYTHONPATH` selection unchanged.
- [ ] For `--autostart` only, create `~/MicroplaiteData/logs/` and append stdout/stderr to `autostart.log`; pass all arguments through to the existing Python entry point.
- [ ] Preserve direct terminal output for ordinary manual launches.
- [ ] Verify that no restart loop is introduced and the launcher propagates the application's exit status.

### Task 3: Reproducible XDG autostart installation

**Files:**
- Create: `rpi5/raspberrypi5/deploy/microplaite-control-autostart.desktop.in`
- Create: `rpi5/raspberrypi5/scripts/install_autostart.py`
- Create: `rpi5/raspberrypi5/tests/test_install_autostart.py`

- [ ] Write failing tests for rendering and installing the desktop entry into an isolated home directory.
- [ ] Make the installer resolve the repository launcher absolutely, render the template, create `~/.config/autostart/`, and write `microplaite-control.desktop` atomically enough for this local configuration task.
- [ ] Ensure the entry executes exactly the existing launcher with `--autostart --fullscreen`, has `Terminal=false`, and does not specify a working directory.
- [ ] Run `desktop-file-validate` against the rendered test artifact.
- [ ] Confirm repeated installation updates the same file rather than creating competing entries.

### Task 4: Documentation and software verification

**Files:**
- Modify: `rpi5/raspberrypi5/README.md`

- [ ] Document manual windowed launch, manual full-screen launch, the autostart installer, installed path, boot log path, manual reconnect behavior, and how to disable autostart without deleting application data.
- [ ] Run targeted launch/autostart tests.
- [ ] Run the complete Python test suite.
- [ ] Run Ruff on every modified Python file.
- [ ] Run `git diff --check` and `desktop-file-validate` on the rendered entry.

### Task 5: Install and validate on the current Raspberry Pi

- [ ] Verify the active graphical environment still runs `lxsession-xdg-autostart` under labwc.
- [ ] Install the entry into `/home/nayo/.config/autostart/microplaite-control.desktop` using the repository installer.
- [ ] Validate the installed entry and record its exact command.
- [ ] Launch the production launcher manually and confirm clean close.
- [ ] Launch with `--fullscreen` in the active graphical session and confirm the window enters full-screen mode.
- [ ] Launch against an intentionally absent serial path and confirm the UI remains open in `DISCONNECTED` with manual reconnect available.
- [ ] Launch with the detected ESP32 port and confirm the application opens normally.
- [ ] Attempt a second launch while the first instance owns the lock and confirm it is refused without disturbing the first instance.
- [ ] Close the running application and confirm no process restarts it during the validation interval.
- [ ] Confirm `~/MicroplaiteData/logs/autostart.log` contains useful startup diagnostics.
- [ ] Do not reboot.

### Task 6: Final Git verification and delivery

- [ ] Confirm only the intended Raspberry Pi files and this approved plan changed; preserve the pre-existing untracked design file.
- [ ] Commit all intended task files once with `Add Raspberry Pi application autostart`.
- [ ] Push `software-v2/autostart-rpi-001` and configure its upstream.
- [ ] Verify local/remote parity and report the requested `AUTOSTART-RPI-001 RESULT`.
