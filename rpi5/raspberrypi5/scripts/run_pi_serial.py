import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microplaite_ui.config import default_serial_port
from microplaite_ui.main import run_gui

if __name__ == "__main__":
    raise SystemExit(run_gui(port=default_serial_port()))
