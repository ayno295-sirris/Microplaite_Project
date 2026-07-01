# Workspace Structure

## Final Source Tree

```text
Microplaite_project/
├── README.md
├── AGENTS.md
├── docs/
│   ├── README.md
│   ├── architecture.md
│   ├── hardware.md
│   ├── communication_protocols.md
│   ├── milestones.md
│   ├── codex_rules.md
│   ├── architecture/
│   │   └── workspace_structure.md
│   └── codex/
│       └── workspace_context.md
├── firmware/
│   └── esp32_platformio/
│       ├── AGENTS.md
│       ├── README.md
│       ├── platformio.ini
│       ├── default_32MB.csv
│       ├── src/
│       │   └── main.cpp
│       ├── include/
│       │   ├── README
│       │   ├── pins.h
│       │   └── configPID.h
│       ├── lib/
│       │   └── README
│       ├── test/
│       │   └── README
│       └── docs/
│           ├── README.md
│           └── hardware/
│               └── heater_control_system.md
└── rpi5/
    └── raspberrypi5/
        ├── AGENTS.md
        ├── README.md
        ├── pyproject.toml
        ├── src/
        └── tests/
```

Generated local folders such as `.pio/`, `.pytest_cache/`, `logs/`, and
`__pycache__/` are not part of the source tree and must stay ignored.

## Separation

The ESP32 and Raspberry Pi projects are separated because they have different
runtime responsibilities and build tools.

The ESP32 owns local embedded hardware control:

- thermocouple acquisition
- heater output
- local PID
- local safety limits
- pump RS485 control
- NeoPixel status

The Raspberry Pi owns supervisor behavior:

- GUI
- screen
- camera
- logging
- high-level orchestration
- serial communication with the ESP32

The Raspberry Pi GUI must not control hardware directly. Hardware actions flow
through control, hardware, and driver layers as milestones introduce them.

## Documentation Locations

- Shared architecture and roadmap docs: `docs/`.
- ESP32 firmware docs: `firmware/esp32_platformio/docs/`.
- Heater hardware/control reference:
  `firmware/esp32_platformio/docs/hardware/heater_control_system.md`.

## Codex Instruction Files

- Global repository rules: `AGENTS.md`.
- ESP32 firmware rules: `firmware/esp32_platformio/AGENTS.md`.
- Raspberry Pi 5 rules: `rpi5/raspberrypi5/AGENTS.md`.
- Compact workspace context: `docs/codex/workspace_context.md`.
