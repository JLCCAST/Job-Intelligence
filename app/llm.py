"""
llm.py -- capa de modelos de lenguaje (varios proveedores)

Todos los agentes que usan IA (Lupa, Pluma, Notario, Brújula) pasan
por aquí. No saben qué proveedor les responde: piden "esta estructura
para el agente X" y esta capa prueba una cadena de modelos en orden:

    1. Los modelos de Gemini del agente (plan gratuito; la cuota es
       POR MODELO, así que cada agente usa los suyos).
    2. Los de respaldo, si los configuraste en el .env:
         Groq   -> gratis y muy rápido (necesita GROQ_API_KEY)
         Ollama -> local en tu PC: sin cuota, pero más lento

Las llamadas usan LiteLLM: la misma función sirve para Gemini, Groq,
Ollama, OpenAI o Claude. Cada modelo se escribe "proveedor/modelo",
por ejemplo "gemini/gemini-3.6-flash" o "groq/openai/gpt-oss-120b".

Cuándo se pasa al siguiente modelo de la cadena:
- Si agotó su cuota DIARIA. Además se recuerda, para no volver a
  gastar una petición en él durante este proceso (Sabueso analiza
  varias ofertas seguidas).
- Si falla por otra razón (caído, sin conexión, JSON inválido), después
  de reintentar los errores temporales (503, 429 por minuto).

La respuesta siempre se valida con Pydantic: un modelo que devuelve
algo fuera de la estructura cuenta como fallo y se prueba el siguiente.
"""

import os
import re
import time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel

from app.schemas import JobExtraction

load_dotenv()

# LiteLLM descarga una tabla de precios desde internet al importarse;
# con esto usa la copia que trae incluida (funciona sin conexión).
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

# Límites del plan gratuito vistos en AI Studio el 2026-10-23
# (peticiones/día): 3.5 Flash Lite 500 · 3.1 Flash Lite 500 ·
# 3.6 / 3.8 / 3 Flash 20. Se cambian desde el .env (ver .env.example).
MODELOS_POR_AGENTE = {
    # extracción: la de más volumen y una tarea simple -> los "lite"
    "lupa": ("gemini/gemini-3.5-flash-lite", "gemini/gemini-3.1-flash-lite"),
    # redacción del CV: la que más importa -> Flash completo
    "pluma": ("gemini/gemini-3.6-flash", "gemini/gemini-3-flash-preview"),
    # plan de estudio: 1 llamada por semana
    "brujula": ("gemini/gemini-3.8-flash", "gemini/gemini-3.6-flash"),
    # explicar los cambios del CV: 1 llamada por CV, mientras esperas.
    # Los "lite" son rápidos (con 3.8 Flash tardó 81 s en 14 cambios) y
    # tienen 500/día; lo que afirma Notario se verifica igual con código.
    "notario": ("gemini/gemini-3.5-flash-lite", "gemini/gemini-3.1-flash-lite", "gemini/gemini-3.8-flash"),
}
MODELO_POR_DEFECTO = "gemini/gemini-3.6-flash"

# Respaldo cuando Gemini no puede (si están configurados en el .env).
# gpt-oss-120b: modelo abierto, en el plan gratuito de Groq (1000
# peticiones/día, visto el 2026-11-06). Llama 3.3 70B pasó a Enterprise.
GROQ_POR_DEFECTO = "groq/openai/gpt-oss-120b"
OLLAMA_URL_POR_DEFECTO = "http://localhost:11434"

TIMEOUT_NUBE = 120   # segundos
TIMEOUT_LOCAL = 600  # Ollama en una laptop sin GPU dedicada es lento


# --------------------------------------------------------------
# Qué modelos usa cada agente
# --------------------------------------------------------------

def _con_proveedor(modelo: str) -> str:
    """Un nombre sin proveedor ("gemini-3.6-flash") se asume de Gemini."""
    return modelo if "/" in modelo else f"gemini/{modelo}"


def _lista(valor: str) -> list[str]:
    return [_con_proveedor(m.strip()) for m in valor.split(",") if m.strip()]


def modelos_para(agente: str) -> list[str]:
    """
    Modelos principales del agente, en orden. El .env manda:
    LLM_MODELOS_<AGENTE> > GEMINI_MODELO_<AGENTE> > GEMINI_MODELO > los del agente.
    """
    for variable in (f"LLM_MODELOS_{agente.upper()}", f"GEMINI_MODELO_{agente.upper()}", "GEMINI_MODELO"):
        valor = os.environ.get(variable)
        if valor:
            return _lista(valor)
    return list(MODELOS_POR_AGENTE.get(agente, (MODELO_POR_DEFECTO,)))


def modelo_para(agente: str) -> str:
    """El modelo preferido del agente (el primero de su lista)."""
    return modelos_para(agente)[0]


def modelos_de_respaldo() -> list[str]:
    """
    LLM_RESPALDO manda si está definido (vacío = sin respaldo). Si no,
    se arma solo con lo que configuraste: Groq si hay GROQ_API_KEY y
    Ollama si hay OLLAMA_MODELO.
    """
    valor = os.environ.get("LLM_RESPALDO")
    if valor is not None:
        return _lista(valor)
    respaldo = []
    if os.environ.get("GROQ_API_KEY"):
        modelo = os.environ.get("GROQ_MODELO") or GROQ_POR_DEFECTO
        respaldo.append(modelo if modelo.startswith("groq/") else f"groq/{modelo}")
    if os.environ.get("OLLAMA_MODELO"):
        respaldo.append(f"ollama_chat/{os.environ['OLLAMA_MODELO']}")
    return respaldo


def cadena_para(agente: str) -> list[str]:
    """Todo lo que se puede probar para un agente: sus modelos y luego el respaldo."""
    cadena: list[str] = []
    for modelo in modelos_para(agente) + modelos_de_respaldo():
        if modelo not in cadena:
            cadena.append(modelo)
    return cadena


# --------------------------------------------------------------
# Errores
# --------------------------------------------------------------

# Esperas (segundos) antes de reintentar errores temporales: 503
# (saturado) o 429 por minuto. En la prueba real de Sabueso aparecieron
# seguidos, en ráfaga.
ESPERAS_REINTENTO = (5, 20)
MARCAS_ERROR_TEMPORAL = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "overloaded")

# El tope DIARIO no se arregla esperando segundos. Gemini lo marca con
# "...PerDay..." y Groq con "requests per day (RPD)".
_CUOTA_DIARIA = re.compile(r"PerDay|per day", re.IGNORECASE)


def es_cuota_diaria_agotada(error: object) -> bool:
    return _CUOTA_DIARIA.search(str(error)) is not None


# Modelos que ya agotaron su cuota diaria en este proceso.
_agotados_hoy: set[str] = set()


# --------------------------------------------------------------
# Llamada a un modelo (el único punto que sale a internet)
# --------------------------------------------------------------

def _instruccion_json(schema: type[BaseModel]) -> str:
    import json
    return (
        "\n\nResponde SOLO con un objeto JSON válido, sin texto antes ni después, "
        "que cumpla este JSON Schema:\n" + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    )


def _completar(modelo: str, prompt: str, schema: type[BaseModel]) -> str:
    """
    Una llamada a un modelo, vía LiteLLM. Devuelve el texto (JSON).
    Gemini tiene salida estructurada nativa (se le pasa el schema); a
    los demás se les pide JSON y el schema va en el prompt.
    """
    import litellm

    litellm.suppress_debug_info = True
    litellm.telemetry = False

    nativo = modelo.startswith("gemini/")
    if nativo and not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError(
            "GEMINI_API_KEY no está configurada. Revisa tu archivo .env "
            "(copia .env.example y completa tu key)."
        )
    local = modelo.startswith(("ollama/", "ollama_chat/"))
    kwargs = {
        "model": modelo,
        "messages": [{"role": "user", "content": prompt if nativo else prompt + _instruccion_json(schema)}],
        "response_format": schema if nativo else {"type": "json_object"},
        "timeout": TIMEOUT_LOCAL if local else TIMEOUT_NUBE,
        "num_retries": 0,  # los reintentos los maneja _intentar
    }
    if local:
        kwargs["api_base"] = os.environ.get("OLLAMA_URL") or OLLAMA_URL_POR_DEFECTO
    respuesta = litellm.completion(**kwargs)
    return respuesta.choices[0].message.content or ""


def _limpiar_json(texto: str) -> str:
    """Algunos modelos envuelven el JSON en ```json ... ```."""
    texto = texto.strip()
    bloque = re.match(r"^```(?:json)?\s*(.*?)\s*```$", texto, flags=re.DOTALL)
    return bloque.group(1) if bloque else texto


def _intentar(modelo: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Un modelo, con reintentos solo para errores temporales."""
    for espera in (*ESPERAS_REINTENTO, None):
        try:
            texto = _completar(modelo, prompt, schema)
            return schema.model_validate_json(_limpiar_json(texto))
        except Exception as exc:
            temporal = any(marca in str(exc) for marca in MARCAS_ERROR_TEMPORAL)
            if espera is None or not temporal or es_cuota_diaria_agotada(exc):
                raise
            time.sleep(espera)


def _avisar_respaldo(agente: str, modelo: str) -> None:
    """Deja en la actividad de la app que se usó un modelo de respaldo."""
    try:
        from app.agents import eventos
        eventos.registrar(agente, f"Usé el modelo de respaldo {modelo}: los principales no estaban disponibles.", "ok")
    except Exception:
        pass  # informativo: nunca debe romper una llamada


def _generar_para(agente: str, prompt: str, schema: type[BaseModel]) -> tuple[BaseModel, str]:
    """
    Prueba la cadena del agente en orden. Devuelve (datos, modelo usado).
    Si todos fallan, lanza un error con el motivo de cada uno.
    """
    cadena = cadena_para(agente)
    # Los agotados hoy se saltan; si están todos agotados, se intenta el
    # último igual para que el error diga por qué.
    candidatos = [m for m in cadena if m not in _agotados_hoy] or cadena[-1:]
    errores = []
    for i, modelo in enumerate(candidatos):
        try:
            datos = _intentar(modelo, prompt, schema)
        except Exception as exc:
            if es_cuota_diaria_agotada(exc):
                _agotados_hoy.add(modelo)
            errores.append(f"({modelo}) {exc}")
            if i == len(candidatos) - 1:
                raise RuntimeError(" | ".join(errores)) from exc
            continue
        if modelo not in modelos_para(agente):
            _avisar_respaldo(agente, modelo)
        return datos, modelo
    raise RuntimeError("No hay modelos configurados para este agente.")


# --------------------------------------------------------------
# API para los agentes
# --------------------------------------------------------------

@dataclass
class ResultadoEstructurado:
    success: bool
    data: Optional[BaseModel] = None
    error: Optional[str] = None
    modelo: Optional[str] = None  # qué modelo respondió


def generar_estructurado(prompt: str, schema: type[BaseModel], agente: str) -> ResultadoEstructurado:
    """
    Llamada con salida estructurada para cualquier agente. Nunca lanza
    excepciones hacia el agente: devuelve éxito (y qué modelo respondió)
    o el motivo del fallo.
    """
    try:
        datos, modelo = _generar_para(agente, prompt, schema)
        return ResultadoEstructurado(success=True, data=datos, modelo=modelo)
    except Exception as exc:
        return ResultadoEstructurado(success=False, error=f"Error llamando a la IA: {exc}")


# --------------------------------------------------------------
# Lupa: extracción de requisitos de una oferta
# --------------------------------------------------------------

@dataclass
class ExtractionResult:
    success: bool
    data: Optional[JobExtraction] = None
    error: Optional[str] = None


PROMPT_TEMPLATE = """\
Analiza el siguiente texto de una oferta laboral y extrae la información
solicitada de forma ESTRICTA:

- No inventes tecnologías, niveles ni requisitos que no estén explícitos
  o claramente implícitos en el texto.
- Cada tecnología detectada debe incluir la frase textual exacta
  (evidence_text) de donde la extrajiste.
- Si el texto indica que la oferta ya no está disponible, está cerrada
  o cubierta, responde is_offer_available=false y technologies=[].

Sobre company_name:
- Debe ser el nombre PROPIO de la empresa (ej. "Banco Pichincha",
  "Ferreyros"), tal como aparece escrito en el texto.
- Descripciones genéricas y anónimas ("importante empresa del rubro
  retail", "prestigiosa entidad financiera", "empresa líder del
  sector") NO son nombres: en ese caso responde 'no_especificado'.
- No deduzcas la empresa a partir del rubro, del puesto ni de las
  tecnologías mencionadas.

Sobre source_name:
- Responde un portal SOLO si el texto indica que la oferta fue
  PUBLICADA ahí (ej. "publicado en LinkedIn", "postula vía
  Computrabajo").
- Que el texto mencione un portal por otro motivo NO cuenta. Por
  ejemplo, "mantener tu perfil de LinkedIn actualizado" es un
  requisito para el candidato, no la fuente de la oferta.
- Ante cualquier duda, responde 'no_especificado'.

Texto de la oferta:
---
{texto}
---
"""


def extract_job_info(cleaned_text: str) -> ExtractionResult:
    resultado = generar_estructurado(PROMPT_TEMPLATE.format(texto=cleaned_text), JobExtraction, agente="lupa")
    if not resultado.success:
        return ExtractionResult(success=False, error=resultado.error)
    return ExtractionResult(success=True, data=resultado.data)
