# Milestones

## M0 - Repository skeleton
Goal: create the project structure and documentation only.
Verification:
- Folder tree exists.
- AGENTS.md exists.
- docs/architecture.md exists.
- No hardware logic implemented.
- No GUI implemented.
- No PID implemented.
- No ESP32 firmware implemented.

## M1 - Raspberry Pi 5 bring-up and remote development
Goal: prepare the Raspberry Pi 5 as the supervisor machine and make host-side development practical from the PC.
Verification:
- Raspberry Pi OS is installed and the Pi boots on the local screen.
- Network access is stable on the Pi.
- SSH access from the development PC works.
- VS Code Remote SSH can open the Raspberry Pi workspace.
- The project repository is available on the Pi.

## M2 - Host Python baseline
Goal: add simple Raspberry Pi Python config and logging for the supervisor application.
Verification:
- Config values are centralized.
- Logging starts from `app/main.py`.
- No hardware access yet.

## M3 - ESP32-S3 PlatformIO workspace
Goal: create a minimal PlatformIO project for the ESP32-S3 dev board.
Scope:
- Create `platformio.ini` for the selected ESP32-S3 board.
- Keep `setup()` and `loop()` short and explicit.
- Create a clean main firmware entry point, pin definitions, shared configuration, and placeholder modules.
Verification:
- PlatformIO project exists under `../esp32_project`.
- The ESP32-S3 board target is defined explicitly.
- Compilation succeeds.
- Upload to the ESP32-S3 is possible.
- No functional heater logic yet.
- No functional pump logic yet.
- No PID logic yet.

## M4 - Bench power and DIN rail integration
Goal: assemble the first physical bench stack so the Raspberry Pi, ESP32, and power distribution are mounted cleanly and powered safely.
Verification:
- Raspberry Pi, ESP32, and power elements are mounted on the DIN rail assembly.
- Power distribution is documented.
- Common ground and signal wiring paths are defined.
- USB or serial access between Raspberry Pi and ESP32 is physically in place.
- No active heater or pump power stage is required yet.

## M5 - Heater power stage bring-up
Goal: build the heating circuit and validate safe low-level heater actuation from the ESP32.
Verification:
- Heater output stage is wired and documented.
- A safe first switching test is completed with the intended driver path.
- Safety assumptions and power limits are documented.
- No closed-loop temperature control yet.

## M6 - ESP32 heater I/O baseline
Goal: make the ESP32 able to read temperature and drive the heater locally with explicit firmware modules.
Verification:
- Thermocouple reading is isolated in firmware.
- Heater output control is isolated in firmware.
- Local safety limit exists on the ESP32.
- No closed-loop temperature control yet.

## M7 - Raspberry Pi to ESP32 protocol implementation
Goal: implement the first usable serial command path between the Raspberry Pi and the ESP32 for heating-related control and status.
Verification:
- Protocol is documented and implemented.
- Commands are minimal.
- Serial link validation works on the real bench.
- ESP32 answers explicit `OK`, `ERR`, and `STATUS` messages.
- A minimal temperature setpoint command can be transmitted safely.

## M8 - Minimal functional heating control
Goal: make the heating chain concretely usable with a Raspberry Pi setpoint and local ESP32 regulation.
Verification:
- Raspberry Pi can send a temperature setpoint through the host control path.
- ESP32 closes the regulation loop locally.
- Host can read current temperature, setpoint, and heater state.
- GUI still does not talk to hardware directly.
- Safety limit exists locally.

## M9 - ESP32 pump RS485 control
Goal: control the Longer T100/WX10 pump from the ESP32.
Verification:
- Pump protocol is isolated in `esp32_project/lib/pump_rs485`.
- Raspberry Pi never talks directly to the pump.
- Raspberry Pi sends only high-level pump commands to ESP32.

## M10 - ESP32 NeoPixel control
Goal: control NeoPixel status indicators from ESP32.
Verification:
- NeoPixel behavior is isolated.
- Status colors are simple and documented.

## M11 - Raspberry Pi camera integration
Goal: integrate Raspberry Pi HQ Camera or Arducam.
Verification:
- Camera driver is isolated.
- GUI does not access camera driver directly.

## M12 - Process controller on Raspberry Pi
Goal: coordinate ESP32, camera, and logging.
Verification:
- UI calls process_controller only.
- Hardware calls remain isolated.

## M13 - Minimal GUI
Goal: expose manual controls and status display.
Verification:
- GUI does not access serial ports, camera driver, ESP32 driver, pump, heater, or NeoPixel directly.
- GUI calls only `control/` or `app/`.

## M14 - Experiment logging and recipe foundation
Goal: record experiment data cleanly and prepare the project for future recipes without implementing them in `ui/`.
Verification:
- Logs are timestamped.
- Data files are simple and readable.
- Future experiment sequencing belongs in `services/experiment_runner.py` or `control/process_controller.py`.
