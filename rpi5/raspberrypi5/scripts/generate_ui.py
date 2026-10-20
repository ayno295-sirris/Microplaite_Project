"""Generate PySide6 modules from Qt Designer forms."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FORMS_DIR = PROJECT_DIR / "src" / "microplaite_ui" / "ui" / "forms"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "src" / "microplaite_ui" / "ui" / "generated"


def _uic_command() -> list[str]:
    environment_uic = Path(sys.executable).with_name("pyside6-uic")
    if environment_uic.is_file():
        return [str(environment_uic)]

    path_uic = shutil.which("pyside6-uic")
    if path_uic:
        return [path_uic]

    system_uic = Path("/usr/lib/qt6/libexec/uic")
    if system_uic.is_file():
        return [str(system_uic), "-g", "python"]

    raise RuntimeError("pyside6-uic is not available")


def generate_forms(forms_dir: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    forms = sorted(forms_dir.glob("*.ui"))
    if not forms:
        print(f"No .ui files found in {forms_dir}")
        return []

    command = _uic_command()
    generated_files: list[Path] = []
    for form in forms:
        generated = output_dir / f"ui_{form.stem}.py"
        subprocess.run(
            [*command, "-o", str(generated), str(form)],
            check=True,
        )
        generated_files.append(generated)
        print(generated)
    return generated_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forms-dir", type=Path, default=DEFAULT_FORMS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    generate_forms(args.forms_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
