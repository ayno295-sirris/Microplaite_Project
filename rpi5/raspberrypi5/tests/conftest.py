from pathlib import Path
import sys

import pytest


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


@pytest.fixture(autouse=True)
def isolate_preferences(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MICROPLAITE_PREFERENCES_PATH", str(tmp_path / "preferences.json"))
