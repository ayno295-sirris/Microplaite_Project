# Raspberry Pi 5 Codex Instructions

This project is the Raspberry Pi 5 supervisor skeleton for the microfluidic test
bench.

## Current Purpose

Detected code scope:

- `src/main.py`: supervisor entry point
- `src/config.py`: environment-driven configuration
- `src/logger.py`: console and file logging
- `tests/`: pytest coverage for config and logging startup

No GUI, camera, GPIO, pump, heater, or ESP32 serial control is implemented yet.

## Setup And Run

Dependency file:

- `pyproject.toml`

Optional development install:

```bash
python -m pip install -e ".[dev]"
```

Run:

```bash
python src/main.py
```

Test:

```bash
python -m pytest
```

## Rules

- Do not hard-code absolute paths.
- Keep Raspberry Pi hardware-specific scripts documented when they are added.
- Preserve capture, analyze, and export workflows if they are added later.
- Do not add direct hardware access before the roadmap reaches that milestone.
- `src/ui/` must not import `pyserial`, `cv2`, GPIO, pump, heater, NeoPixel, or
  ESP32 serial drivers directly.
- Future experiment sequences must live in `src/services/experiment_runner.py`
  or `src/control/process_controller.py`, not in `src/ui/`.
