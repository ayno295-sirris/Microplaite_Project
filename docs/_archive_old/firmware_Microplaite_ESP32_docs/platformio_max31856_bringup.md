# PlatformIO MAX31856 Bring-Up

This project owns its PlatformIO dependencies in `platformio.ini`.
Do not copy Adafruit libraries into `lib/`.

## 1. Confirm Project Configuration

The ESP32-S3 environment must include:

```ini
[env:esp32-s3-devkitc-1]
platform = espressif32
board = esp32-s3-devkitc-1
framework = arduino
lib_ldf_mode = deep+

lib_deps =
    adafruit/Adafruit BusIO@^1.17.4
    adafruit/Adafruit MAX31856 library@^1.2.8
```

`Wire` and `SPI` are Arduino ESP32 framework libraries. They are not installed
manually and are not copied into this repository.

## 2. Clean Generated Cache If Dependency Resolution Looks Wrong

If PlatformIO still compiles an old dependency set or reports `Wire.h` missing,
clean generated files:

```bash
pio run --target clean
```

If the error persists after a clean, delete the generated `.pio` directory and
build again. `.pio` is generated and ignored.

## 3. Build, Upload, Monitor

Run from this directory:

```bash
pio run
pio run --target upload
pio device monitor
```

Codex must not run these commands automatically; hardware execution stays under
user control.

## 4. UART Smoke Test

Send one JSON command per line:

```json
{"id":1,"cmd":"PING"}
{"id":2,"cmd":"STATUS"}
{"id":3,"cmd":"STOP"}
{"id":4,"cmd":"HEATER_SET_TARGET","target_c":37.5}
{"id":5,"cmd":"HEATER_ENABLE"}
{"id":6,"cmd":"HEATER_DISABLE"}
```

`HEATER_ENABLE` should return an error until the MAX31856 has a valid
temperature reading and safety state is not `ERROR`.

`STATUS` includes both `temperature_available` and `temperature_valid`.
`temperature_available=false` means the MAX31856 did not initialize.
`temperature_valid=false` means the MAX31856 initialized but the current reading
is not usable.
`temperature_fault` is the MAX31856 fault mask; `0` means no active fault.

Malformed input should return `ERR` and must not enable hardware:

```text
"id":5,"cmd":"HEATER_ENABLE"
{"cmd":"HEATER_ENABLE"}
{"id":7,"cmd":"UNKNOWN"}
```
