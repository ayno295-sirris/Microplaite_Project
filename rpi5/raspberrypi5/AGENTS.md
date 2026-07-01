# Codex Instructions

## Scope

- These instructions apply to the Raspberry Pi 5 GUI/UART project in `rpi5/raspberrypi5/`.
- Keep Raspberry development inside this directory.
- Do not create a duplicate `raspberrypi5` directory at the repository root.

## Raspberry GUI/UART Target

- Build the GUI in Python with PySide6.
- Target landscape resolution: 1280 x 720.
- Use `pyserial` for serial communication.
- Windows serial port: `COM10`.
- Raspberry Pi serial port: `/dev/serial0`.
- Baudrate: `115200`.

## Architecture

- Use this flow: UI -> AppController -> Esp32Client.
- The GUI must never talk directly to the serial port.
- Use `FakeEsp32Client` for development without an ESP32.
- Use `SerialEsp32Client` for `COM10` or `/dev/serial0`.
- ESP32 owns safety, PID, heating, and sensor logic.
- Raspberry owns interface, supervision, and logs.

## Interface Rules

- STOP must always be very visible.
- The interface must be simple, modern, ergonomic, and usable by a lightly trained lab technician.
- Keep screens clear and direct.

## Coding Rules

- Keep code compact, short, and readable.
- Avoid unnecessary dependencies.
- Do not use Streamlit.
- Do not use Flask.
- Do not add a web server.
- Do not add a database.
- Do not add Teleplot for now.
