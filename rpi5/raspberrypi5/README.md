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
  Timelapse preview, and Camera preview.
- Right panel: large touch actions for `START PID`, `STOP`, `CLEAR ERROR`, and `REFRESH STATUS`.
- Bottom strip: compact status summary and a short log area capped to fit the 1280 x 720 landscape screen.

The layout is optimized for Raspberry Pi Touch Display 2 in 1280 x 720 landscape mode. STOP stays large, red, and always visible.

Pump and Timelapse controls are usable from the UI:

- Pump RPM, START PUMP, STOP PUMP, and PRIME update `AppState.pump` and the Home card locally.
- Timelapse uses `AppController` to set NeoPixel brightness, turn the ring on just before capture,
  and turn it off in `finally` after every capture attempt.
- The Timelapse page provides storage selection, disk free space, interval, NeoPixel power,
  light duration, finite or infinite duration, Start/Stop, Test Capture, Live Video Start/Stop,
  optional live video recording, frame count, last saved file, and `metadata.json`.

The Camera page first tries Picamera2/libcamera full-frame RGB capture for raw 4:3 display.
Qt Multimedia remains the fallback camera path and is used for `video_YYYYMMDD_HHMMSS.mp4`
recording to the selected internal or external storage. It keeps the touchable BACK button and does not add OpenCV.

## Timelapse Manual Test

1. Start the UI on the Raspberry Pi with the camera, ESP32, and NeoPixel connected.
2. Open `Timelapse`, select `Internal Raspberry Pi`, and confirm the displayed path and disk free value.
3. Press `START LIVE VIDEO`, wait for a stable image, then press `TEST CAPTURE`.
4. Confirm the NeoPixel turns on only during the configured light duration and turns off after capture.
5. Confirm `Last file` points to `test_capture_YYYYMMDD_HHMMSS.jpg` and the image opens from that path.
6. Enable `Record video`, choose storage, press `START LIVE`, then `STOP LIVE`, and confirm the
   saved `video_*.mp4` exists in `~/Microplaite/video` or the external disk.
7. Set interval to `10 seconds`, light duration to `1.0 s`, duration to `1 min`, then press `START TIMELAPSE`.
8. Confirm the frame counter increments without UI freeze and the NeoPixel turns off after every frame.
9. Press `STOP` and verify the session folder contains `img_*.jpg` and `metadata.json`.
10. Repeat with `External disk` inserted, then remove or unmount it before start to confirm a clear storage error.

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
- `NEOPIXEL_ON`
- `NEOPIXEL_OFF`
- `NEOPIXEL_BRIGHTNESS <percent>`
- `LOG_ON 200`
- `LOG_OFF`

Pump and NeoPixel support depends on the connected firmware command set.

Reference ESP32 UART documents are copied in `docs/esp32_uart/`.

For a handoff summary of the current UI state and validation status, see
`docs/project_status.md`.

The ESP32 firmware remains the primary safety controller. Do not modify `firmware/Microplaite_ESP32` unless that is explicitly requested.
