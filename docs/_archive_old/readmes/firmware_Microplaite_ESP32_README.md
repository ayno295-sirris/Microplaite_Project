# ESP32 PlatformIO Project

PlatformIO firmware project for the ESP32-S3 embedded controller.

Current scope:

- keep a minimal bootable firmware skeleton
- use PlatformIO as the only firmware workflow
- add heater, protocol, pump, and safety behavior milestone by milestone

This project uses the Arduino framework. The selected hardware target is the
ESP32-S3-DevKitC-1-N32R16V class board configuration.

## Commands

Run from this directory:

```bash
pio run
pio run --target upload
pio device monitor
```

## Documentation

- ESP32 documentation index: `docs/README.md`
- PlatformIO MAX31856 bring-up: `docs/platformio_max31856_bringup.md`
- Heater hardware/control reference:
  `docs/hardware/heater_control_system.md`

The heater documentation is the authoritative hardware and control reference for
Codex sessions working on heater behavior.
