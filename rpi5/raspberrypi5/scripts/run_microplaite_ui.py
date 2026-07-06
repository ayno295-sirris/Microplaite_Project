from argparse import ArgumentParser
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microplaite_ui.config import DEFAULT_BAUDRATE, default_serial_port
from microplaite_ui.esp32.serial_client import SerialEsp32Client
from microplaite_ui.main import run_gui


def main() -> int:
    parser = ArgumentParser(description="Run the Microplaite ESP32 UART GUI.")
    parser.add_argument(
        "--port",
        default=default_serial_port(),
        help="Serial port, for example COM10, /dev/ttyUSB0, /dev/ttyACM0, or /dev/serial0.",
    )
    args = parser.parse_args()
    return run_gui(SerialEsp32Client(args.port, DEFAULT_BAUDRATE))


if __name__ == "__main__":
    raise SystemExit(main())
