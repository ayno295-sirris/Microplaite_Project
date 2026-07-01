"""GUI entry points."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from microplaite_ui.config import DEFAULT_BAUDRATE, default_serial_port
from microplaite_ui.core.controller import AppController
from microplaite_ui.esp32.client import Esp32Client
from microplaite_ui.esp32.serial_client import SerialEsp32Client
from microplaite_ui.ui.main_window import MainWindow


def run_gui(client: Esp32Client | None = None) -> int:
    app = QApplication(sys.argv)
    controller = AppController(client or SerialEsp32Client(default_serial_port(), DEFAULT_BAUDRATE))
    window = MainWindow(controller)
    window.show()
    return app.exec()


def main() -> None:
    raise SystemExit(run_gui())


if __name__ == "__main__":
    main()
