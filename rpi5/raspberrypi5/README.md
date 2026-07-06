# Microplaite Raspberry GUI

Python/PySide6 interface for supervising the Microplaite ESP32 over UART. The normal application starts in real serial mode and tries to connect to the ESP32. The ESP32 firmware is read-only and keeps primary responsibility for safety, PID, heating, thermocouple reading, STOP, and fault handling.

## Architecture

- GUI: PySide6, fixed 1280 x 720 on Windows.
- Trend graph: minimal `pyqtgraph` temperature curve.
- Flow: UI -> AppController -> Esp32Client.
- `SerialEsp32Client`: UART client for `COM10` on Windows, auto-detected ESP32 USB serial on Raspberry Pi, or `/dev/serial0` fallback.
- `FakeEsp32Client`: kept only for unit tests and internal development checks.
- Raspberry/PC role: interface, supervision, recent logs, and operator actions.

The GUI never talks directly to the serial port.
Live updates use `LOG_ON 200` and one Qt timer that reads available serial lines without blocking. There is no worker thread or internal event bus. `REFRESH STATUS` remains a manual diagnostic button.

## Main Screen

- Header: title, serial port state, and global state (`DISCONNECTED`, `IDLE`, `RUNNING`, `ERROR`).
- Left panel: large current temperature and a five-minute live temperature graph fed by `LOG,time_ms,temp,target,heater,gpio14,mode,sensor,fault`.
- Center panel: target, mode, heater output, sensor state, fault state, last error, Pump preview,
  NeoPixel preview, and Camera preview.
- Right panel: large touch actions for `START PID`, `STOP`, `CLEAR ERROR`, and `REFRESH STATUS`.
- Bottom strip: compact status summary and a short log area capped to fit the 1280 x 720 landscape screen.

The layout is optimized for Raspberry Pi Touch Display 2 in 1280 x 720 landscape mode. STOP stays large, red, and always visible.

Pump and NeoPixel controls are usable locally in the UI to prepare the future firmware integration:

- Pump RPM, START PUMP, STOP PUMP, and PRIME update `AppState.pump` and the Home card locally.
- NeoPixel ON/OFF and brightness update `AppState.neopixel`, the visual ring preview, and the Home card locally.
- No Pump or NeoPixel UART command is sent while those commands are absent from
  `docs/esp32_uart/serial_commands.md`.
- The controller logs a clear local message such as `Pump control not supported by current firmware`
  or `NeoPixel control not supported by current firmware` instead of calling `Esp32Client`.

The Camera page shows the first detected USB camera through Qt Multimedia. It keeps the touchable BACK
button and does not add OpenCV.

## Run

From `rpi5/raspberrypi5`:

```powershell
python -m pip install -e .
```

Recommended Windows run. This tries `COM10` by default:

```powershell
python scripts\run_microplaite_ui.py
```

Explicit Windows COM10 run:

```powershell
python scripts\run_microplaite_ui.py --port COM10
```

Raspberry Pi run. This auto-detects the ESP32 on `/dev/serial/by-id/*`, `/dev/ttyACM*`, or `/dev/ttyUSB*`, then falls back to `/dev/serial0`:

```bash
python scripts/run_microplaite_ui.py
```

Manual Raspberry Pi port override:

```bash
python scripts/run_microplaite_ui.py --port /dev/ttyUSB0
MICROPLAITE_SERIAL_PORT=/dev/ttyUSB0 python scripts/run_microplaite_ui.py
```

Install a clickable Raspberry Pi desktop/menu shortcut:

```bash
python scripts/install_desktop_shortcut.py
```

If the ESP32 is not connected, the UI shows the selected port as disconnected and `ESP32 not connected`. It does not switch to fake data.

## UART

- Windows port: `COM10`
- Raspberry Pi USB port: auto-detected from `/dev/serial/by-id/*`, `/dev/ttyACM*`, or `/dev/ttyUSB*`
- Raspberry Pi fallback port: `/dev/serial0`
- Baudrate: `115200`
- Line ending: `\n`

Commands used by the GUI:

- `STATUS`
- `READ_TEMP`
- `CLEAR_ERROR`
- `SET_TARGET 37.50`
- `SET_PID 8 0.03 20`
- `SET_PID_LIMIT 15`
- `PID_ON`
- `PID_OFF`
- `STOP`
- `LOG_ON 200`
- `LOG_OFF`

No Pump or NeoPixel command is currently emitted by the GUI.

Reference ESP32 UART documents are copied in `docs/esp32_uart/`.

For a handoff summary of the current UI state and validation status, see
`docs/project_status.md`.

The ESP32 firmware remains the primary safety controller. Do not modify `firmware/Microplaite_ESP32` unless that is explicitly requested.
