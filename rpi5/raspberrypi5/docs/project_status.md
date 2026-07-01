# Microplaite Raspberry GUI - project status

Last updated: 2026-06-12

This document is the handoff note for resuming the Raspberry Pi 5 GUI work.
Work in this project must stay inside `rpi5/raspberrypi5`.

## Critical constraints

- Do not modify `firmware/Microplaite_ESP32`.
- Do not run `pio run`, `pio upload`, firmware flashing, or hardware firmware tests unless explicitly requested.
- Do not create another `raspberrypi5` directory at the repository root.
- The old IDE path `raspberrypi5/...` may still appear in tabs, but the active project path is `rpi5/raspberrypi5`.
- Do not invent UART commands. The active UART command reference is `docs/esp32_uart/serial_commands.md`.

## Current architecture

- GUI stack: Python + PySide6.
- Graphs: `pyqtgraph`.
- Serial transport: `pyserial`.
- Flow: UI -> `AppController` -> `Esp32Client`.
- The GUI does not talk directly to the serial port.
- Live serial polling uses `QTimer`; no worker thread is used.
- ESP32 remains responsible for safety, PID, heating, thermocouple reading, STOP, and faults.
- Raspberry/PC GUI is responsible for interface, supervision, local UI state, and logs.

## Key files

- Entry point: `src/microplaite_ui/main.py`
- Runtime config: `src/microplaite_ui/config.py`
- Main UI: `src/microplaite_ui/ui/main_window.py`
- QSS: `src/microplaite_ui/ui/styles.py`
- Controller: `src/microplaite_ui/core/controller.py`
- State: `src/microplaite_ui/core/state.py`
- UART client interface: `src/microplaite_ui/esp32/client.py`
- Serial client: `src/microplaite_ui/esp32/serial_client.py`
- Fake client: `src/microplaite_ui/esp32/fake_client.py`
- Parser: `src/microplaite_ui/esp32/parser.py`
- Tests: `tests/test_main.py`, `tests/test_parser.py`, `tests/test_config.py`

## Current UI state

The app is a fixed 1280 x 720 PySide6 HMI using a `QStackedWidget`.

Pages:

- HomePage
- TemperaturePage
- ThermalControlPage
- PumpPage
- NeoPixelPage
- CameraPage

HomePage:

- Large temperature card with mini live graph.
- Thermal control card.
- Pump, NeoPixel, and Camera preview cards.
- Action column: START PID, STOP, CLEAR ERROR, REFRESH STATUS.
- Bottom status line and compact log box.

TemperaturePage:

- Compact detail header with BACK, title, port, status pill, and STOP.
- Current temperature, target, heater output.
- Large live temperature graph.
- Bottom cards: Mode, Sensor, Fault, Last error.

ThermalControlPage:

- Compact detail header with BACK, title, port, status pill, and STOP.
- Top row: Temperature control, Setpoint, Heater output.
- Middle row:
  - PID parameters card on the left, `450 x 290`.
  - Live response preview card on the right, `770 x 290`.
  - Thermal graph inside the graph card is about `732 x 230` in offscreen validation.
- Bottom row: Sensor, Fault, GPIO14, Last error.
- The read-only explanatory text was removed from the PID card.
- PID values are shown as two columns: name on the left, value on the right.

PumpPage:

- Controls are usable locally even though firmware Pump commands are not documented.
- RPM slider and spinbox are synchronized, range `0..300`, default `120`.
- START PUMP sets local state to running and simulates actual RPM as target RPM.
- STOP PUMP sets local state to stopped and actual RPM to `0`.
- PRIME logs a local unsupported message.
- No Pump UART command is sent while unsupported.

NeoPixelPage:

- Controls are usable locally even though firmware NeoPixel commands are not documented.
- ON/OFF buttons update local `AppState.neopixel.enabled`.
- Brightness slider and spinbox are synchronized, range `0..100`, default `80`.
- Ring preview reacts visually to ON/OFF and brightness.
- Home NeoPixel card reflects local ON/OFF and brightness.
- No NeoPixel UART command is sent while unsupported.

CameraPage:

- Full-screen placeholder preview.
- Only BACK and the dark preview area are visible.
- No STOP on this page.
- No status panel, future list, OpenCV dependency, or real camera integration.

## State model

`AppState` contains:

- `ThermalState`
- `PumpState`
- `NeoPixelState`
- `CameraState`

Important defaults:

- Temperature history: `deque(maxlen=1500)`, about 5 minutes at 200 ms.
- Pump: `supported=False`, `running=False`, `actual_rpm=0`, `target_rpm=120`.
- NeoPixel: `supported=False`, `enabled=True`, `brightness_percent=80`.
- Camera: `supported=False`, `available=False`.

System status derives as:

- `DISCONNECTED` if not connected.
- `ERROR` if mode is ERROR, fault is true, or last error is not NONE.
- `RUNNING` if mode is PID or heater output is above 0.
- `IDLE` otherwise.

## UART behavior

Commands currently used by the GUI:

- `STATUS`
- `READ_TEMP`
- `CLEAR_ERROR`
- `SET_TARGET <temp_c>`
- `SET_PID <kp> <ki> <kd>`
- `SET_PID_LIMIT <percent>`
- `PID_ON`
- `PID_OFF`
- `STOP`
- `LOG_ON 200`
- `LOG_OFF`

Startup behavior:

- The GUI sends `STATUS` once.
- If connected, it sends `LOG_ON 200`.
- A `QTimer` polls pending serial lines every 200 ms.
- `STATUS` is not sent every 200 ms; `REFRESH STATUS` remains manual.

Unsupported local-only behavior:

- Pump actions update `AppState.pump` and log `Pump control not supported by current firmware`.
- Pump PRIME logs `Pump prime not supported by current firmware`.
- NeoPixel actions update `AppState.neopixel` and log `NeoPixel control not supported by current firmware`.
- These local-only actions do not call `Esp32Client`.

## Parser state

The parser supports at least:

- CSV live log:
  `LOG,time_ms,temp_c,target_c,heater_output_percent,gpio14,mode,sensor_valid,fault`
- Word/pair style `OK STATUS ...`
- `OK TEMP ...`
- `ERR ...`
- PID fields including `PID`, `PID_LIMIT`, and `PID_INTEGRAL`.

## How to run

From `rpi5/raspberrypi5`:

```powershell
python -m pip install -e .
python scripts\run_microplaite_ui.py --port COM10
```

Fake UI for development without hardware:

```powershell
python scripts\run_windows_fake.py
```

Raspberry Pi serial target:

```bash
python scripts/run_microplaite_ui.py --port /dev/serial0
```

## Validation status

Last known validation after the latest UI layout work:

```powershell
python -m pytest
```

Result: `28 passed`.

```powershell
python -m compileall src scripts tests
```

Result: OK.

## Git/worktree notes

The repository worktree is currently dirty and includes many pre-existing changes outside this Raspberry UI work.
In particular, `firmware/Microplaite_ESP32` shows modified/untracked files in `git status`, but those firmware files were not modified during the recent GUI layout and UI-state changes.

When resuming:

- Inspect `git status --short rpi5\raspberrypi5 firmware\Microplaite_ESP32`.
- Treat firmware changes as pre-existing unless the user explicitly asks to work on firmware.
- Keep edits scoped to `rpi5/raspberrypi5` for Raspberry GUI tasks.

## Likely next work

- Real visual QA on a 1280 x 720 display or offscreen screenshot.
- Hardware serial smoke test on `COM10`, only if explicitly requested.
- Future Pump/NeoPixel UART integration only after commands are documented in `docs/esp32_uart/serial_commands.md`.
- Future camera integration only after a separate camera dependency/design decision.
