from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
GENERATOR = PROJECT_DIR / "scripts" / "generate_ui.py"


def _run_generator(forms_dir: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--forms-dir",
            str(forms_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def test_generator_converts_ui_form_to_named_pyside6_module(tmp_path: Path) -> None:
    forms_dir = tmp_path / "forms"
    output_dir = tmp_path / "generated"
    forms_dir.mkdir()
    (forms_dir / "recipe_page.ui").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>RecipePage</class>
 <widget class="QWidget" name="RecipePage"/>
 <resources/>
 <connections/>
</ui>
""",
        encoding="utf-8",
    )

    result = _run_generator(forms_dir, output_dir)

    generated = output_dir / "ui_recipe_page.py"
    assert result.returncode == 0, result.stderr
    assert generated.exists()
    content = generated.read_text(encoding="utf-8")
    assert "from PySide6.QtCore import" in content
    assert "class Ui_RecipePage(object):" in content
    assert str(generated) in result.stdout


def test_generator_accepts_empty_forms_directory(tmp_path: Path) -> None:
    forms_dir = tmp_path / "forms"
    output_dir = tmp_path / "generated"
    forms_dir.mkdir()

    result = _run_generator(forms_dir, output_dir)

    assert result.returncode == 0, result.stderr
    assert output_dir.is_dir()
    assert "No .ui files found" in result.stdout
