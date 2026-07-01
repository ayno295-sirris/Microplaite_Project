# Microplaite Project

Global repository for the Microplaite microfluidic test bench.

## Structure

```text
Microplaite_project/
  .git/
  AGENTS.md
  README.md
  docs/
  firmware/
    Microplaite_ESP32/
      platformio.ini
      src/
      include/
      lib/
      test/
  rpi5/
    raspberrypi5/
```

## Active Projects

- ESP32 firmware: `firmware/Microplaite_ESP32/`
- Raspberry Pi 5 project: `rpi5/raspberrypi5/`
- Active documentation: `docs/`
- Archived old documentation: `docs/_archive_old/`

## Current Development Priority

Autonomous ESP32 heating at 37.50 C.

Out of scope for the current priority:

- UART control
- Raspberry Pi control
- graphical interface

## Repository Rules

- Use the single Git repository at the project root.
- Use the single active `AGENTS.md` at the project root.
- Do not restructure the PlatformIO project.
- Do not move `platformio.ini`, `src/`, `include/`, `lib/`, or `test/`.
- Do not force-push to GitHub without manual validation.
