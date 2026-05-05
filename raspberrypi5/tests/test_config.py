from pathlib import Path

from config import APP_NAME
from config import DEFAULT_LOG_DIR
from config import load_config


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
