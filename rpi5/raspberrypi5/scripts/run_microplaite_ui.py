import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microplaite_ui.config import default_serial_port
from microplaite_ui.main import run_gui


def main() -> int:
    parser = ArgumentParser(description="Run the Microplaite ESP32 UART GUI.")
    parser.add_argument(
        "--port",
        default=default_serial_port(),
        help="Serial port, for example COM10, /dev/ttyUSB0, /dev/ttyACM0, or /dev/serial0.",
    )
    args = parser.parse_args()
    return run_gui(port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
