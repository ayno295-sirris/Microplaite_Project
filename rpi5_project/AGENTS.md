# Coding Rules For This Project

This project controls a Raspberry Pi based microfluidic test bench.

The Raspberry Pi is the supervisor:
- GUI
- screen
- camera
- logging
- high-level process orchestration
- serial communication with ESP32

The ESP32 is the embedded hardware controller:
- thermocouple K acquisition
- heater output through MOSFET DFR0457
- local temperature PID
- Longer T100/WX10 pump through RS485
- NeoPixel
- local safety limits

Architecture rule:
The GUI never controls hardware directly.

Current Raspberry Pi codebase:
- `app/` contains entry point and configuration
- `services/` contains logging support
- future `control/`, `hardware/`, `drivers/`, and `ui/` layers must be added only when the roadmap reaches them

Allowed Raspberry Pi flow:
UI -> control -> hardware -> drivers

Allowed embedded-controller flow:
UI -> process_controller -> embedded_control -> EmbeddedControllerClient -> Esp32SerialDriver -> ESP32

Allowed camera flow:
UI -> process_controller -> camera_control -> Camera -> CameraDriver

Forbidden:
- `ui/` must not import `pyserial`
- `ui/` must not import `cv2` directly
- `ui/` must not access GPIO
- `ui/` must not access pump RS485
- `ui/` must not access heater control
- `ui/` must not access NeoPixel control
- `ui/` must not access ESP32 serial directly
- `drivers/` must not import `ui/`
- `../esp32_project` must not depend on Raspberry Pi GUI logic

Write code like an engineer building a test bench:
- Prefer simple, explicit code over abstract patterns
- Keep code short and direct
- Do not introduce frameworks unless requested
- Do not create generic plugin systems
- Do not use inheritance unless it clearly simplifies hardware interfaces
- Keep files focused
- One file = one clear responsibility
- Use clear names over clever code
- Add comments only when they explain hardware behavior, protocol details, timing, or safety assumptions
- Do not silently catch exceptions
- Fail visibly and log hardware communication errors
- Do not create a full simulation framework
- Small mocks for unit tests are allowed
- Keep public APIs small:
  - `connect()`
  - `disconnect()`
  - `start()`
  - `stop()`
  - `read()`
  - `set_value()`
  - `get_status()`
- Do not refactor working code unless explicitly asked
- Avoid premature optimization
- Avoid over-engineering
- Do not make the code verbose
- Do not implement functionality before the corresponding milestone

Experiment recipes are not implemented yet.
Future experiment sequences must not be implemented inside `ui/`.
They must belong to `services/experiment_runner.py` or `control/process_controller.py`.
