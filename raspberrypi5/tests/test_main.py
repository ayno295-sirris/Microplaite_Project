from pathlib import Path
import logging

from main import main


def test_main_creates_log_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APP_NAME", "test_app")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    main()

    logging.shutdown()
    assert (tmp_path / "logs" / "microplaite.log").exists()
