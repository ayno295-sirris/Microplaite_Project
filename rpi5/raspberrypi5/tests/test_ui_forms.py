from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: I001
    QApplication,
    QComboBox,
    QFrame,
    QPushButton,
    QWidget,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]
FORMS_DIR = PROJECT_DIR / "src" / "microplaite_ui" / "ui" / "forms"
GENERATOR = PROJECT_DIR / "scripts" / "generate_ui.py"


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recipes_form_builds_operator_controls(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    result = subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--forms-dir",
            str(FORMS_DIR),
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )

    generated = output_dir / "ui_recipes_page.py"
    assert result.returncode == 0, result.stderr
    assert generated.exists()

    module = _load_module(generated)
    app = QApplication.instance() or QApplication([])
    page = QWidget()
    ui = module.Ui_RecipesPage()
    ui.setupUi(page)
    page.show()
    app.processEvents()

    assert page.findChild(QComboBox, "recipe_combo") is not None
    assert page.findChild(QPushButton, "recipe_start_button").text() == "START RECIPE"
    assert page.findChild(QPushButton, "recipe_stop_button").text() == "STOP RECIPE"
    assert page.findChild(QPushButton, "recipes_global_stop_button").text() == "STOP"
    assert page.findChild(QPushButton, "recipes_back_button").text() == "BACK"
    assert page.findChild(QFrame, "recipes_card").size().toTuple() == (900, 430)

    page.close()
