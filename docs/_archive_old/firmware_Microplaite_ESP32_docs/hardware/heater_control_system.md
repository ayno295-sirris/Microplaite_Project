# Heater Control System

This is the canonical path for the ESP32 heater hardware and control reference.

## Known Safety Constraints

- Heater output must be off at boot.
- No automatic heating after reset.
- Heater enable commands are rejected until the temperature reading is valid.
- Heater target commands are accepted only from 20.0 C to 37.5 C.
- Heater output is forced off and heater enable state is cleared when safety
  state is `ERROR`.
- Heater output is forced off and heater enable state is cleared if the
  temperature reading becomes invalid while heating is enabled.
- Pin assignments are centralized in `include/pins.h`.
- PID values are centralized in `include/configPID.h`.
- Do not use GPIO35, GPIO36, or GPIO37.
- Respect warning at 37.8 C and error at 38.0 C.
- Current development behavior at 38.0 C is logging `"ERROR"` on entry to the
  error state, forcing heater output off, and requiring a new explicit
  `HEATER_ENABLE` command after the safety state recovers.
- If the MAX31856 reading becomes invalid during heating, the heater is disabled
  and requires a new explicit `HEATER_ENABLE` after readings become valid again.

## Current ESP32 Implementation

- Heater control signal: GPIO14 (`PIN_HEATER_PWM`).
- Heater driver: DFRobot DFR0457 MOSFET power controller.
- Temperature sensor: MAX31856 thermocouple K reader over software SPI.
- Target temperature default: 37.5 C.
- Target temperature command range: 20.0 C to 37.5 C.
- Control mode: slow time-window PWM.
- PWM window: 2000 ms.
- Full output is requested when temperature is at least 0.5 C below target.
- Output falls linearly to 0% between target - 0.5 C and target.
- Output is 0% at or above target.

## Wiring Reference

DFR0457 logic side:

- DFR0457 `GND` to ESP32 `GND`.
- DFR0457 logic `VCC` to 5 V.
- DFR0457 `SIG` to ESP32 GPIO14.
- Do not connect 5 V to an ESP32 GPIO.

DFR0457 power side:

- 24 V supply positive to DFR0457 `VIN`.
- Cartridge heater positive through the DFR0457 switched output path.
- 24 V supply ground must share common ground with ESP32/DFR0457 logic ground.

MAX31856 software SPI:

- SCK: GPIO12.
- MISO: GPIO13.
- MOSI: GPIO11.
- CS: GPIO10.
- DRDY: GPIO9 reserved.
- FAULT: GPIO8 reserved.

## UART Heater Commands

```json
{"id":4,"cmd":"HEATER_SET_TARGET","target_c":37.5}
{"id":5,"cmd":"HEATER_ENABLE"}
{"id":6,"cmd":"HEATER_DISABLE"}
```

`HEATER_ENABLE` is rejected unless the MAX31856 temperature reading is valid and
safety state is not `ERROR`.
