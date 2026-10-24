"""Hosted functions must not write into the read-only application bundle."""

from pathlib import Path

from backend.config import PROJECT_DIR, build_settings


def test_vercel_uses_temporary_data_and_model_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("FLOWLAB_DATA_DIR", raising=False)
    monkeypatch.delenv("FLOWLAB_MODEL", raising=False)
    monkeypatch.setattr("backend.config.gettempdir", lambda: str(tmp_path))

    settings = build_settings()

    assert settings.data_dir == (tmp_path / "flowlab").resolve()
    assert settings.database_path.is_relative_to(settings.data_dir)
    assert settings.upload_dir.is_relative_to(settings.data_dir)
    assert settings.processed_dir.is_relative_to(settings.data_dir)
    assert Path(settings.model_name) == settings.data_dir / "yolo11n.pt"


def test_explicit_paths_override_vercel_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("FLOWLAB_DATA_DIR", str(tmp_path / "custom"))
    monkeypatch.setenv("FLOWLAB_MODEL", str(tmp_path / "custom.pt"))

    settings = build_settings()

    assert settings.data_dir == (tmp_path / "custom").resolve()
    assert settings.model_name == str(tmp_path / "custom.pt")


def test_local_defaults_are_preserved(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("FLOWLAB_DATA_DIR", raising=False)
    monkeypatch.delenv("FLOWLAB_MODEL", raising=False)

    settings = build_settings()

    assert settings.data_dir == (PROJECT_DIR / "data").resolve()
    assert settings.model_name == "yolo11n.pt"
