# Codex Instructions

## Repository

- One active Git repository only: `.git` at the `Microplaite_project/` root.
- Root repository instructions live in this file: `Microplaite_project/AGENTS.md`.
- Raspberry GUI/UART instructions live in `rpi5/raspberrypi5/AGENTS.md`.
- Active documentation lives in `docs/`.
- Archived old documentation lives in `docs/_archive_old/`.
- Do not create another Git repository.
- Do not create another `raspberrypi5` directory at the repository root.
- Do not commit, push, force-push, or change the Git remote unless explicitly requested.

## Active Structure

- ESP32 PlatformIO firmware: `firmware/Microplaite_ESP32/`.
- Raspberry Pi 5 project: `rpi5/raspberrypi5/`.
- Root documentation: `docs/`.

## ESP32 Firmware Protection

- The ESP32 firmware is read-only unless the user explicitly asks to modify it.
- The current ESP32 firmware is validated and must not be disturbed casually.
- Do not modify these paths unless explicitly requested:
  - `firmware/Microplaite_ESP32/platformio.ini`
  - `firmware/Microplaite_ESP32/src/`
  - `firmware/Microplaite_ESP32/include/`
  - `firmware/Microplaite_ESP32/lib/`
  - `firmware/Microplaite_ESP32/test/`
- Do not modify firmware `.cpp`, `.h`, or `.hpp` files unless explicitly requested.
- Do not run `pio run`, `pio upload`, monitor, flash, or hardware firmware tests unless explicitly requested.

## Raspberry Development

- Raspberry Pi development must stay inside `rpi5/raspberrypi5/`.
- Follow `rpi5/raspberrypi5/AGENTS.md` for Raspberry GUI/UART work.

## Coding Rules

- Keep code simple, compact, readable, and testable.
- Avoid over-engineering and broad refactors.
- Do not modify business code for repository-organization tasks.
- Keep generated artifacts ignored.
- Do not delete files without explicit instruction.
