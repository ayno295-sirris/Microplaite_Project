# ESP32 PlatformIO Codex Instructions

This directory is the ESP32-S3 PlatformIO project.

The ESP32-S3 is a low-level hardware controller.
The Raspberry Pi 5 is the high-level supervisor.

The Raspberry Pi sends commands to the ESP32 over UART / USB Serial.
The ESP32 executes only safe, local, hardware-level actions.

---

## Build And Device Commands

These commands exist, but Codex must not run them automatically.

* Build: `pio run`
* Upload: `pio run --target upload`
* Monitor: `pio device monitor`

Rules:

* Do not run `pio run`.
* Do not run `pio run --target upload`.
* Do not run `pio device monitor`.
* Do not build, upload or monitor unless explicitly requested by the user.
* Leave all hardware execution under user control.
* You may tell the user which command to run manually.

---

## Project Facts

* Framework: Arduino
* Board: ESP32-S3-DevKitC-1-N32R16V
* PlatformIO project root: `firmware/esp32_platformio/`
* Heater documentation path: `docs/hardware/heater_control_system.md`

---

## System Responsibilities

Raspberry Pi 5:

* UI
* recipes
* experiment orchestration
* camera
* logging
* data export
* high-level decisions

ESP32-S3:

* heater control
* thermocouple reading
* local thermal safety
* pump control
* NeoPixel/status output
* watchdog
* UART command parsing
* command acknowledgment
* emergency stop behavior

Do not duplicate Raspberry Pi supervisor logic in the ESP32 firmware.

---

## Firmware Architecture

The UART command interface is the central entry point.

Use this flow:

```text
SerialCommandService
  -> CommandDispatcher
      -> AppState
      -> SafetyService
      -> HeaterService
      -> TemperatureService
      -> PumpService
      -> StatusLedService
      -> WatchdogService
```

`main.cpp` must stay minimal:

```cpp
#include <Arduino.h>
#include "app/App.h"

App app;

void setup() {
  app.begin();
}

void loop() {
  app.update();
}
```

---

## Preferred Structure

Use this structure where relevant:

```text
include/
  pins.h
  configPID.h
  configSafety.h
  configSerial.h

src/
  main.cpp

  app/
    App.h
    App.cpp
    AppState.h

  services/
    HeaterService.h
    HeaterService.cpp
    TemperatureService.h
    TemperatureService.cpp
    PumpService.h
    PumpService.cpp
    SafetyService.h
    SafetyService.cpp
    StatusLedService.h
    StatusLedService.cpp
    WatchdogService.h
    WatchdogService.cpp

  comm/
    SerialCommandService.h
    SerialCommandService.cpp
    CommandDispatcher.h
    CommandDispatcher.cpp
    CommandTypes.h
```

Do not create empty files just for structure symmetry.
Create only files required by the current implementation.

---

## Coding Style

Write firmware like an embedded engineer.

Priorities:

1. Minimal code.
2. Functional hardware behavior.
3. Safe boot state.
4. Explicit pins.
5. Simple services.
6. Non-blocking loop.
7. No over-engineering.

Rules:

* Keep `main.cpp` minimal.
* Put hardware logic in simple services.
* Prefer small classes or plain functions.
* Avoid inheritance.
* Avoid factories.
* Avoid service registries.
* Avoid template-heavy code.
* Avoid dependency injection.
* Avoid verbose comments.
* Avoid decorative logs.
* Avoid new dependencies unless strictly needed.
* Do not rewrite unrelated code.
* Do not do broad refactors for small changes.

---

## Service API Style

Services should expose simple methods.

Examples:

```cpp
void begin();
void update();
void stop();
```

For heater:

```cpp
void setTargetC(float targetC);
void enable();
void disable();
bool enabled() const;
```

For pump:

```cpp
void setRpm(float rpm);
void start();
void stop();
bool running() const;
```

No hardware output should change inside constructors.
Hardware outputs must be initialized explicitly in `begin()`.

---

## UART Protocol

Use a simple line-based protocol.

Preferred format: JSON Lines.

Each command is one line ending with `\n`.

Each command must include:

* `id`
* `cmd`

Minimum command set:

```json
{"id":1,"cmd":"PING"}
{"id":2,"cmd":"STATUS"}
{"id":3,"cmd":"STOP"}
```

Recommended hardware commands:

```json
{"id":4,"cmd":"HEATER_SET_TARGET","target_c":37.0}
{"id":5,"cmd":"HEATER_ENABLE"}
{"id":6,"cmd":"HEATER_DISABLE"}
{"id":7,"cmd":"PUMP_SET_RPM","rpm":20.0}
{"id":8,"cmd":"PUMP_START"}
{"id":9,"cmd":"PUMP_STOP"}
```

Response format:

```json
{"id":1,"type":"OK","cmd":"PING"}
{"id":2,"type":"STATUS","temp_c":36.8,"heater_enabled":false,"pump_running":false,"safety":"OK"}
{"id":3,"type":"ERR","cmd":"UNKNOWN","error":"UNKNOWN_COMMAND"}
```

UART rules:

* Parser must be non-blocking.
* Do not wait indefinitely for serial data.
* Always reply to valid commands.
* Unknown commands return `ERR`.
* Malformed lines return `ERR`.
* Missing `id` returns `ERR`.
* Limit input line length.
* If the input buffer overflows, clear it and return an error.
* Do not let malformed UART data enable hardware.
* Do not put command parsing inside hardware services.

---

## Safety Rules

* Heater must be OFF at boot.
* Pump must be STOPPED at boot.
* Do not start automatic heating after reset.
* Do not start the pump automatically after reset.
* Do not enable heater output before temperature reading is valid.
* `STOP` must immediately disable heater and stop pump.
* Unknown or malformed commands must fail safely.
* If communication is lost, firmware must remain in the last safe local state.
* If safety state becomes `ERROR`, hardware must remain safe unless behavior is explicitly changed by the user.
* Respect warning at `37.8 C`.
* Respect error at `38.0 C`.
* Current development behavior at `38.0 C` is logging `"ERROR"` only unless explicitly changed.
* Do not change heater safety behavior without updating `docs/hardware/heater_control_system.md`.

GPIO rules:

* Keep pin assignments centralized in `include/pins.h`.
* Keep PID values centralized in `include/configPID.h`.
* Do not use GPIO35.
* Do not use GPIO36.
* Do not use GPIO37.

---

## AppState

Use a simple `AppState` to expose the current hardware state to `STATUS`.

Suggested fields:

```cpp
struct AppState {
  bool heaterEnabled;
  float heaterTargetC;
  float temperatureC;
  bool temperatureValid;

  bool pumpRunning;
  float pumpRpm;

  SafetyLevel safetyLevel;
  uint32_t uptimeMs;
};
```

Suggested safety enum:

```cpp
enum class SafetyLevel {
  OK,
  WARNING,
  ERROR
};
```

Keep the state model simple.
Do not create a complex state machine unless required.

---

## Timing Rules

* Use `millis()` for periodic updates.
* Avoid runtime `delay()`.
* Keep UART parsing non-blocking.
* Keep sensor read timing explicit.
* Do not use FreeRTOS tasks unless strictly required.

---

## Pump Rules

The peristaltic pump is controlled by the ESP32-S3.

Rules:

* Pump control belongs in `PumpService`.
* Do not place pump protocol code in `main.cpp`.
* Do not start pump at boot.
* Do not implement dosing recipes in ESP32.
* Do not implement timed pump profiles in ESP32.
* Do not implement calibration unless explicitly requested.
* The Raspberry Pi handles experiment-level pump sequences.

---

## Heater Rules

Heater control belongs in `HeaterService`.

Rules:

* Heater output OFF at boot.
* Heating disabled until explicit UART command.
* PID constants in `include/configPID.h`.
* Safety thresholds in config or safety service.
* No automatic heating after reset.
* Do not modify safety behavior without updating documentation.

---

## Serial Command Priorities

Initial implementation priority:

1. `PING`
2. `STATUS`
3. `STOP`
4. heater enable/disable/set target
5. pump start/stop/set rpm

Do not implement recipe logic before the command backbone is clean.

---

## Documentation Rules

Update documentation only when behavior changes.

Required documentation updates:

* heater safety behavior changes;
* pin assignment changes;
* pump wiring/protocol changes;
* serial command format changes;
* safety threshold changes.

Do not create long documentation for trivial changes.

---

## Response Rules For Codex

When answering the user:

* Be concise.
* State changed files.
* State what was implemented.
* State what remains manual.
* Do not include long explanations unless asked.
* Do not claim the code was built unless explicitly asked to run `pio run`.
* Do not claim upload success.
* Do not claim hardware validation.

Preferred response format:

```text
Changed:
- ...

Implemented:
- ...

UART:
- ...

Safety:
- ...

Manual check:
- `pio run`
- `pio run --target upload`
- `pio device monitor`
```

---

## Minimalism Policy

Before adding code, ask:

1. Is this needed for the current hardware test?
2. Can this be done with fewer files?
3. Can this be done without a new dependency?
4. Can this be done without changing unrelated modules?
5. Does this preserve safe boot behavior?

If unclear, implement the smallest safe version.
