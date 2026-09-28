"""GUI entry points."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtWidgets import QApplication

from microplaite_ui.config import DEFAULT_BAUDRATE, default_serial_port
from microplaite_ui.core.controller import AppController
from microplaite_ui.esp32.client import Esp32Client
from microplaite_ui.esp32.v2_client import V2Client
from microplaite_ui.esp32.v2_serial_transport import SerialV2Transport
from microplaite_ui.esp32.v2_session import V2Session
from microplaite_ui.esp32.v2_ui_client import V2UiClient
from microplaite_ui.ui.main_window import MainWindow


def create_v2_ui_client(
    port: str | None = None,
    baudrate: int = DEFAULT_BAUDRATE,
) -> V2UiClient:
    transport = SerialV2Transport(port or default_serial_port(), baudrate)
    client = V2Client(transport)
    return V2UiClient(V2Session(client))


def _acquire_instance_lock() -> QLockFile | None:
    runtime_location = QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)
    lock_directory = (
        Path(runtime_location)
        if runtime_location
        else Path.home() / ".cache" / "microplaite"
    )
    lock_directory.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_directory / "microplaite-control.lock"))
    if not lock.tryLock(0):
        return None
    return lock


def run_gui(
    client: Esp32Client | None = None,
    port: str | None = None,
    *,
    fullscreen: bool = False,
) -> int:
    app = QApplication(sys.argv)
    instance_lock = _acquire_instance_lock()
    if instance_lock is None:
        print("Microplaite Control is already running.", file=sys.stderr)
        return 2
    selected_client = client or create_v2_ui_client(port)
    controller = AppController(selected_client)
    if getattr(selected_client, "requires_active_session", False):
        controller.open_connection()
    window = MainWindow(controller)
    if fullscreen:
        window.showFullScreen()
    else:
        window.show()
    return app.exec()


def main() -> None:
    raise SystemExit(run_gui())


if __name__ == "__main__":
    main()
