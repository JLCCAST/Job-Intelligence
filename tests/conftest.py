import pytest

from app import llm
from app.agents import eventos


@pytest.fixture(autouse=True)
def actividad_aislada(monkeypatch, tmp_path):
    """Ningún test escribe en el registro real de actividad (data/actividad.jsonl)."""
    monkeypatch.setattr(eventos, "RUTA_ACTIVIDAD", tmp_path / "actividad.jsonl")


@pytest.fixture(autouse=True)
def sin_llm_real(monkeypatch):
    """
    Ningún test llama a un LLM de verdad (gastaría tu cuota y sería
    lento). Si a un test le falta su LLM falso, falla rápido y claro.
    """
    def bloqueado(*args, **kwargs):
        raise RuntimeError("Llamada real a un LLM desde un test: usa un falso con monkeypatch.")

    monkeypatch.setattr(llm, "_completar", bloqueado)
    monkeypatch.setattr(llm, "_agotados_hoy", set())
    # Las cadenas de modelos no dependen de tu .env real.
    for variable in ("LLM_RESPALDO", "GROQ_API_KEY", "GROQ_MODELO", "OLLAMA_MODELO", "GEMINI_MODELO"):
        monkeypatch.delenv(variable, raising=False)
