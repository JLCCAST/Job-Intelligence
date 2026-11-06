"""
Tests de la capa de IA (app/llm.py): qué modelos usa cada agente,
cuándo pasa al respaldo y cómo valida lo que responde cada modelo.
Sin red: se reemplaza _completar, el único punto que sale a internet.
"""

import pytest
from pydantic import BaseModel

from app import llm

# Se guarda antes de que el fixture global (conftest) lo bloquee.
_COMPLETAR_REAL = llm._completar


class Datos(BaseModel):
    nombre: str


@pytest.fixture
def respuestas(monkeypatch):
    """_completar falso: cada modelo responde lo que diga el diccionario."""
    por_modelo: dict[str, object] = {}
    usados: list[str] = []

    def fake_completar(modelo, prompt, schema):
        usados.append(modelo)
        r = por_modelo.get(modelo, '{"nombre": "ok"}')
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(llm, "_completar", fake_completar)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    return por_modelo, usados


def test_cada_agente_tiene_sus_modelos_y_el_env_manda(monkeypatch):
    for var in ("GEMINI_MODELO_LUPA", "GEMINI_MODELO_PLUMA", "LLM_MODELOS_PLUMA"):
        monkeypatch.delenv(var, raising=False)
    assert llm.modelo_para("lupa") != llm.modelo_para("pluma")
    assert llm.modelo_para("pluma").startswith("gemini/")

    monkeypatch.setenv("GEMINI_MODELO", "modelo-global")      # sin proveedor: se asume Gemini
    assert llm.modelo_para("pluma") == "gemini/modelo-global"

    monkeypatch.setenv("GEMINI_MODELO_PLUMA", "modelo-pluma")
    assert llm.modelo_para("pluma") == "gemini/modelo-pluma"
    assert llm.modelo_para("lupa") == "gemini/modelo-global"

    monkeypatch.setenv("LLM_MODELOS_PLUMA", "groq/llama-x, ollama_chat/qwen")
    assert llm.modelos_para("pluma") == ["groq/llama-x", "ollama_chat/qwen"]


def test_el_respaldo_se_arma_con_lo_que_configuraste(monkeypatch):
    monkeypatch.delenv("GEMINI_MODELO_LUPA", raising=False)
    monkeypatch.delenv("LLM_MODELOS_LUPA", raising=False)
    assert llm.modelos_de_respaldo() == []

    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("OLLAMA_MODELO", "qwen2.5:7b")
    assert llm.modelos_de_respaldo() == [llm.GROQ_POR_DEFECTO, "ollama_chat/qwen2.5:7b"]
    # La cadena: primero los de Gemini del agente, luego el respaldo.
    assert llm.cadena_para("lupa") == [*llm.MODELOS_POR_AGENTE["lupa"], llm.GROQ_POR_DEFECTO, "ollama_chat/qwen2.5:7b"]

    monkeypatch.setenv("LLM_RESPALDO", "")                     # vacío = sin respaldo
    assert llm.modelos_de_respaldo() == []


def test_reintenta_solo_errores_temporales(respuestas, monkeypatch):
    por_modelo, usados = respuestas
    errores = [RuntimeError("503 UNAVAILABLE"), RuntimeError("503 UNAVAILABLE")]

    def temporal_dos_veces(modelo, prompt, schema):
        usados.append(modelo)
        if errores:
            raise errores.pop()
        return '{"nombre": "ok"}'

    monkeypatch.setattr(llm, "_completar", temporal_dos_veces)
    assert llm._intentar("gemini/x", "p", Datos).nombre == "ok"
    assert len(usados) == 3

    def error_permanente(modelo, prompt, schema):
        usados.append(modelo)
        raise ValueError("400 bad")

    usados.clear()
    monkeypatch.setattr(llm, "_completar", error_permanente)
    with pytest.raises(ValueError):
        llm._intentar("gemini/x", "p", Datos)
    assert len(usados) == 1   # un error que no es temporal no se reintenta


def test_si_un_modelo_agota_su_cuota_diaria_pasa_al_siguiente_y_lo_recuerda(respuestas, monkeypatch):
    por_modelo, usados = respuestas
    monkeypatch.setenv("GEMINI_MODELO_LUPA", "lite-a,lite-b")
    por_modelo["gemini/lite-a"] = RuntimeError("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier")

    datos, modelo = llm._generar_para("lupa", "p", Datos)
    assert (datos.nombre, modelo) == ("ok", "gemini/lite-b")
    # La segunda vez ya no pierde una petición con el modelo agotado.
    llm._generar_para("lupa", "p", Datos)
    assert usados == ["gemini/lite-a", "gemini/lite-b", "gemini/lite-b"]


def test_si_gemini_no_puede_responde_el_respaldo(respuestas, monkeypatch):
    por_modelo, usados = respuestas
    monkeypatch.setenv("GEMINI_MODELO_PLUMA", "flash")
    monkeypatch.setenv("LLM_RESPALDO", "groq/llama,ollama_chat/qwen")
    por_modelo["gemini/flash"] = RuntimeError("429 RESOURCE_EXHAUSTED PerDay")
    por_modelo["groq/llama"] = "esto no es JSON"           # responde mal: cuenta como fallo
    por_modelo["ollama_chat/qwen"] = '```json\n{"nombre": "local"}\n```'

    r = llm.generar_estructurado("p", Datos, agente="pluma")
    assert r.success and r.data.nombre == "local" and r.modelo == "ollama_chat/qwen"
    assert usados == ["gemini/flash", "groq/llama", "ollama_chat/qwen"]


def test_si_todos_fallan_el_error_dice_por_que_y_sigue_siendo_de_cuota_diaria(respuestas, monkeypatch):
    por_modelo, _ = respuestas
    monkeypatch.setenv("GEMINI_MODELO_LUPA", "lite-a,lite-b")
    por_modelo["gemini/lite-a"] = RuntimeError("429 RESOURCE_EXHAUSTED PerDay")
    por_modelo["gemini/lite-b"] = RuntimeError("429 RESOURCE_EXHAUSTED PerDay")

    with pytest.raises(RuntimeError) as error:
        llm._generar_para("lupa", "p", Datos)
    assert llm.es_cuota_diaria_agotada(error.value)   # Sabueso se detiene con esto
    assert "lite-a" in str(error.value) and "lite-b" in str(error.value)

    r = llm.generar_estructurado("p", Datos, agente="lupa")
    assert not r.success and "PerDay" in r.error


def test_cuota_diaria_de_groq_tambien_se_reconoce():
    assert llm.es_cuota_diaria_agotada("Rate limit reached on requests per day (RPD): Limit 1000")
    assert not llm.es_cuota_diaria_agotada("429 Too Many Requests: requests per minute")


def test_a_los_modelos_que_no_son_gemini_se_les_pide_json_con_el_schema(monkeypatch):
    llamadas = []

    class Respuesta:
        class _Choice:
            class message:
                content = '{"nombre": "ok"}'
        choices = [_Choice]

    import litellm
    monkeypatch.setattr(litellm, "completion", lambda **kw: llamadas.append(kw) or Respuesta)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    # El fixture global bloquea _completar; aquí se prueba el original,
    # con litellm.completion reemplazado (no sale a internet).
    for modelo in ("groq/llama", "gemini/flash", "ollama_chat/qwen"):
        assert _COMPLETAR_REAL(modelo, "Prompt", Datos) == '{"nombre": "ok"}'

    groq, gemini, ollama = llamadas
    assert groq["response_format"] == {"type": "json_object"} and "JSON Schema" in groq["messages"][0]["content"]
    assert gemini["response_format"] is Datos and gemini["messages"][0]["content"] == "Prompt"
    assert ollama["api_base"] == llm.OLLAMA_URL_POR_DEFECTO and ollama["timeout"] == llm.TIMEOUT_LOCAL


def test_sin_gemini_api_key_el_error_es_claro(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY no está configurada"):
        _COMPLETAR_REAL("gemini/flash", "Prompt", Datos)
