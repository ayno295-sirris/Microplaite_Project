from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microplaite_ui.config import DEFAULT_BAUDRATE, DEFAULT_PI_PORT
from microplaite_ui.esp32.serial_client import SerialEsp32Client
from microplaite_ui.main import run_gui


if __name__ == "__main__":
    raise SystemExit(run_gui(SerialEsp32Client(DEFAULT_PI_PORT, DEFAULT_BAUDRATE)))
