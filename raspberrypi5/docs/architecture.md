# Architecture

## Objective
Provide a minimal control stack for a Raspberry Pi based microfluidic test bench.

## Raspberry Pi / ESP32 split
The Raspberry Pi supervises the system.
The ESP32 owns the hardware that must stay local.

## Raspberry Pi role
- GUI
- screen
- camera
- logging
- high-level orchestration
- serial communication with the ESP32

## ESP32 role
- thermocouple K acquisition
- heater output through MOSFET DFR0457
- local temperature PID
- Longer T100/WX10 pump control over RS485
- NeoPixel
- local safety limits

## Current Raspberry Pi code
- `src/main.py`: entry point
- `src/config.py`: environment-driven configuration
- `src/logger.py`: logging setup

## Future Raspberry Pi layers
- `src/control/`: process coordination
- `src/hardware/`: host-side hardware wrappers
- `src/drivers/`: low-level serial and camera drivers
- `src/ui/`: GUI surface

## Firmware location
- `../esp32_platformio/`: isolated ESP32-S3 PlatformIO firmware

## Development environments
- Raspberry Pi app: developed in a VS Code Remote SSH workspace on the Raspberry Pi 5
- ESP32 firmware: developed in the separate `esp32_platformio/` PlatformIO workspace and uploaded over USB

## GUI rule
The GUI never controls hardware directly.

## Allowed flows
- UI -> control -> hardware -> drivers
- UI -> process_controller -> embedded_control -> EmbeddedControllerClient -> Esp32SerialDriver -> ESP32
- UI -> process_controller -> camera_control -> Camera -> CameraDriver

## Forbidden flows
- UI importing or using hardware drivers directly
- UI accessing GPIO, pump, heater, NeoPixel, or ESP32 serial directly
- drivers importing GUI code
- `../esp32_platformio` depending on Raspberry Pi GUI logic
