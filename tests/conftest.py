import pytest

from app.agents import eventos


@pytest.fixture(autouse=True)
def actividad_aislada(monkeypatch, tmp_path):
    """Ningún test escribe en el registro real de actividad (data/actividad.jsonl)."""
    monkeypatch.setattr(eventos, "RUTA_ACTIVIDAD", tmp_path / "actividad.jsonl")
