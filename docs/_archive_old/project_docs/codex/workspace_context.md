# Workspace Context For Codex

## ESP32 Role

The ESP32-S3 is the embedded hardware controller. Its PlatformIO project lives
in `firmware/esp32_platformio/` and uses the Arduino framework.

The ESP32 owns local hardware behavior:

- thermocouple K acquisition
- heater output through MOSFET DFR0457
- local temperature PID
- local safety limits
- Longer T100/WX10 pump over RS485
- NeoPixel status output

## Raspberry Pi 5 Role

The Raspberry Pi 5 project lives in `rpi5/raspberrypi5/`.

Current scope is a minimal Python supervisor skeleton:

- configuration loading
- console and file logging
- no GUI yet
- no hardware access yet

Future Raspberry Pi code must keep the GUI away from hardware drivers. Use the
documented control and driver flow when those layers are introduced.

## Heater Subsystem

The heater is controlled locally by the ESP32. The Raspberry Pi may later send
high-level setpoints or stop commands, but it must not directly drive the
heater, GPIO, MOSFET, or local PID loop.

Canonical heater documentation path:

`firmware/esp32_platformio/docs/hardware/heater_control_system.md`

If that file still contains the pending-content note, populate it from the
provided source document before making heater implementation changes.

## Safety Constraints

- Heater output must be off at boot.
- No automatic heating after reset.
- Pin assignments must stay centralized in `include/pins.h`.
- PID values must stay centralized in `include/configPID.h`.
- Do not use GPIO35, GPIO36, or GPIO37.
- Respect warning at 37.8 C and error at 38.0 C.
- Current development behavior at 38.0 C is logging `"ERROR"` only unless
  explicitly changed.
- Do not change heater safety logic without updating the heater documentation.

## Look Here First

1. `README.md`
2. `AGENTS.md`
3. `docs/architecture/workspace_structure.md`
4. `firmware/esp32_platformio/AGENTS.md`
5. `rpi5/raspberrypi5/AGENTS.md`
6. `firmware/esp32_platformio/docs/hardware/heater_control_system.md`
