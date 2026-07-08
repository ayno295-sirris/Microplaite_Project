# AGENTS.md — Temporary ESP32 Heater Work

## Scope

This is a temporary local instruction file for work inside the PlatformIO ESP32 firmware only.

Current working folder:

```text
firmware/Microplaite_ESP32/
```

Main objective for this session:

Build and test the autonomous ESP32 heating control.

No Raspberry Pi.
No GUI.
No UART implementation today.
No global repository reorganization.

---

## Critical rule

Do not change the PlatformIO project structure.

Do not move or rename:

* `platformio.ini`
* `src/`
* `include/`
* `lib/`
* `test/`
* the current firmware folder

Do not restructure the project.

Do not perform a global refactor.

Modify only what is strictly necessary for the heater test.

---

## Coding style

Keep code short, direct and readable.

Prefer:

* small functions;
* explicit names;
* simple control flow;
* minimal files;
* clear serial logs;
* local changes.

Avoid:

* over-engineering;
* large classes;
* generic frameworks;
* deep abstractions;
* verbose comments;
* duplicated logic;
* rewriting working code only for style.

Comments should explain why, not what.

---

## Hardware

Firmware target:

* ESP32 under PlatformIO / Arduino
* MAX31856 thermocouple reader over SPI
* DFRobot DFR0457 MOSFET driver
* 24 VDC heater cartridge
* heater command pin: GPIO14

The ESP32 must control the heater locally and safely.

---

## Target behavior

The firmware must run autonomously.

At boot:

* heater OFF;
* serial logs active;
* sensor initialized;
* control loop ready.

Temperature control:

* target temperature: 37.50 °C;
* first control mode: ON/OFF with hysteresis;
* heater ON if temperature is below 37.25 °C;
* heater OFF if temperature is above 37.75 °C.

Do not implement PID unless explicitly requested.

---

## Safety rules

The heater must be OFF:

* at boot;
* after reset;
* if MAX31856 initialization fails;
* if thermocouple reading is invalid;
* if thermocouple fault is detected;
* if measured temperature exceeds the configured safety limit;
* if an internal error is detected.

Safety must be handled locally by the ESP32.

Never rely on Raspberry Pi, UART, or GUI for heater safety.

---

## Serial output

Serial logs must be simple and useful.

Print periodically:

* measured temperature;
* target temperature;
* heater state;
* sensor validity;
* fault or error state;
* control mode.

Avoid excessive logging.

---

## Implementation order

Use this order:

1. inspect existing firmware structure;
2. identify the least risky integration points;
3. validate current build before changes;
4. add or verify MAX31856 reading;
5. add or verify GPIO14 heater control;
6. add ON/OFF hysteresis control;
7. add safety cutoffs;
8. compile with PlatformIO;
9. keep the final diff small.

---

## Validation

After every firmware change, run:

```bash
pio run
```

Before physical heater testing, confirm in code and logs:

* heater is OFF at boot;
* GPIO14 is not active before initialization;
* sensor fault keeps heater OFF;
* overtemperature keeps heater OFF;
* serial logs are readable.

---

## Out of scope today

Do not work on:

* Raspberry Pi code;
* GUI;
* UART protocol;
* PID tuning;
* repository cleanup;
* documentation cleanup;
* GitHub push;
* global project structure.

Those will be handled later from the repository root.
