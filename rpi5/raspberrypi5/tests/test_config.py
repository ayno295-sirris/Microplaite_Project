from pathlib import Path

from config import APP_NAME
from config import DEFAULT_PI_PORT
from config import DEFAULT_WINDOWS_PORT
from config import DEFAULT_LOG_DIR
from config import SERIAL_PORT_ENV
from config import default_serial_port
from config import load_config
from microplaite_ui import config as ui_config


class FakePort:
    def __init__(
        self,
        device: str,
        description: str = "",
        manufacturer: str = "",
        product: str = "",
        vid: int | None = None,
        pid: int | None = None,
    ) -> None:
        self.device = device
        self.name = Path(device).name
        self.description = description
        self.hwid = ""
        self.manufacturer = manufacturer
        self.product = product
        self.interface = ""
        self.vid = vid
        self.pid = pid


def test_load_config_uses_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_DIR", raising=False)

    config = load_config()

    assert config.app_name == APP_NAME
    assert config.log_level == "INFO"
    assert config.log_dir == DEFAULT_LOG_DIR


def test_load_config_reads_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_NAME", "bench")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "custom_logs"))

    config = load_config()

    assert config.app_name == "bench"
    assert config.log_level == "DEBUG"
    assert config.log_dir == tmp_path / "custom_logs"


def test_default_serial_port_uses_platform(monkeypatch) -> None:
    monkeypatch.delenv(SERIAL_PORT_ENV, raising=False)
    monkeypatch.setattr("microplaite_ui.config.platform.system", lambda: "Windows")
    assert default_serial_port() == DEFAULT_WINDOWS_PORT

    monkeypatch.setattr("microplaite_ui.config.platform.system", lambda: "Linux")
    monkeypatch.setattr("microplaite_ui.config.detect_esp32_serial_port", lambda: None)
    assert default_serial_port() == DEFAULT_PI_PORT


def test_default_serial_port_uses_environment_override(monkeypatch) -> None:
    monkeypatch.setenv(SERIAL_PORT_ENV, "/dev/ttyUSB9")
    monkeypatch.setattr("microplaite_ui.config.platform.system", lambda: "Linux")

    assert default_serial_port() == "/dev/ttyUSB9"


def test_default_serial_port_uses_detected_linux_usb_port(monkeypatch) -> None:
    monkeypatch.delenv(SERIAL_PORT_ENV, raising=False)
    monkeypatch.setattr("microplaite_ui.config.platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "microplaite_ui.config.detect_esp32_serial_port",
        lambda: "/dev/ttyUSB0",
    )

    assert default_serial_port() == "/dev/ttyUSB0"


def test_choose_esp32_port_prefers_stable_usb_link() -> None:
    ports = [
        FakePort("/dev/ttyS0", description="GPIO serial"),
        FakePort(
            "/dev/ttyUSB0",
            description="CP2102N USB to UART Bridge Controller",
            vid=0x10C4,
            pid=0xEA60,
        ),
        FakePort(
            "/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller-if00-port0",
            description="CP2102N USB to UART Bridge Controller",
            manufacturer="Silicon Labs",
            product="CP2102N USB to UART Bridge Controller",
            vid=0x10C4,
            pid=0xEA60,
        ),
    ]

    assert ui_config._choose_esp32_port(ports) == (
        "/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller-if00-port0"
    )
