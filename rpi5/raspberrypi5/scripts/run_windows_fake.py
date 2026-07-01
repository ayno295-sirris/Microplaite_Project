from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from microplaite_ui.esp32.fake_client import FakeEsp32Client
from microplaite_ui.main import run_gui


if __name__ == "__main__":
    raise SystemExit(run_gui(FakeEsp32Client()))
