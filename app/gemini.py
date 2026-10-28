"""
gemini.py

Responsabilidad única: recibir texto limpio (ya procesado por
cleaner.py) y devolver una extracción estructurada usando Gemini
con structured output (response_schema). No decide qué hacer con
el resultado -- eso lo maneja quien llame a esta función.
"""

import os
import time
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel

from app.schemas import JobExtraction

load_dotenv()  # lee el .env y carga GEMINI_API_KEY como variable de entorno

MODEL_NAME = "gemini-3.6-flash"  # gemini-2.5-flash fue discontinuado (jul 2026);
# no usamos un modelo "Pro": cuota diaria gratuita mucho más baja (Fase 1)

# La cuota gratuita es POR MODELO (el 429 dice "...PerProjectPerModel"):
# cada agente usa sus propios modelos, en orden de preferencia; si el
# primero agota su cuota del día se pasa al siguiente. Límites del plan
# gratuito vistos en AI Studio el 2026-10-23 (peticiones/día):
#     3.5 Flash Lite 500 · 3.1 Flash Lite 500 · 3.6 / 3.8 / 3 Flash 20
# Se cambian desde el .env, separados por coma:
#     GEMINI_MODELO_LUPA=gemini-3.5-flash-lite,gemini-3.1-flash-lite
MODELOS_POR_AGENTE = {
    # extracción: la de más volumen y una tarea simple -> los "lite"
    "lupa": ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite"),
    # redacción del CV: la que más importa -> Flash completo
    "pluma": ("gemini-3.6-flash", "gemini-3-flash-preview"),
    # plan de estudio: 1 llamada por semana
    "brujula": ("gemini-3.8-flash", "gemini-3.6-flash"),
}


def modelos_para(agente: str) -> list[str]:
    """GEMINI_MODELO_<AGENTE> > GEMINI_MODELO > los del agente. Acepta varios separados por coma."""
    valor = os.environ.get(f"GEMINI_MODELO_{agente.upper()}") or os.environ.get("GEMINI_MODELO")
    if valor:
        return [m.strip() for m in valor.split(",") if m.strip()]
    return list(MODELOS_POR_AGENTE.get(agente, (MODEL_NAME,)))


def modelo_para(agente: str) -> str:
    """El modelo preferido del agente (el primero de su lista)."""
    return modelos_para(agente)[0]


# Modelos que ya agotaron su cuota diaria en este proceso: no se
# vuelven a intentar (Sabueso analiza varias ofertas seguidas).
_agotados_hoy: set[str] = set()


def _generar_para(agente: str, **kwargs):
    """
    _generar probando los modelos del agente en orden. Solo salta al
    siguiente si el actual agotó su cuota DIARIA; cualquier otro error
    se propaga. Devuelve (respuesta, modelo usado).
    """
    candidatos = [m for m in modelos_para(agente) if m not in _agotados_hoy] or modelos_para(agente)[-1:]
    for i, modelo in enumerate(candidatos):
        try:
            return _generar(model=modelo, **kwargs), modelo
        except Exception as exc:
            if es_cuota_diaria_agotada(exc) and i < len(candidatos) - 1:
                _agotados_hoy.add(modelo)
                continue
            raise RuntimeError(f"({modelo}) {exc}") from exc

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    """
    Cliente perezoso (lazy): no se crea hasta que realmente se
    necesita, y solo se crea una vez por proceso. Si GEMINI_API_KEY
    no está configurada, falla acá con un mensaje claro, en vez de
    fallar más adelante con un error críptico de la librería.
    """
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY no está configurada. Revisa tu archivo .env "
                "(copia .env.example y completa tu key)."
            )
        _client = genai.Client(api_key=api_key)
    return _client


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


# Esperas (segundos) antes de reintentar cuando Gemini responde 503
# (saturado) o 429 (demasiadas peticiones). Son errores temporales:
# en la prueba real de Sabueso aparecieron seguidos, en ráfaga.
ESPERAS_REINTENTO = (5, 20)
MARCAS_ERROR_TEMPORAL = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")

# El plan gratuito tiene un tope DIARIO (20 peticiones/día para este
# modelo, visto el 2026-10-23). Ese 429 no se arregla esperando
# segundos: reintentar solo gasta... nada, pero alarga la corrida.
MARCA_CUOTA_DIARIA = "PerDay"


def es_cuota_diaria_agotada(error: object) -> bool:
    return MARCA_CUOTA_DIARIA in str(error)


def _generar(**kwargs):
    """generate_content con reintentos solo para errores temporales."""
    for espera in (*ESPERAS_REINTENTO, None):
        try:
            return _get_client().models.generate_content(**kwargs)
        except Exception as exc:
            temporal = any(marca in str(exc) for marca in MARCAS_ERROR_TEMPORAL)
            if espera is None or not temporal or es_cuota_diaria_agotada(exc):
                raise
            time.sleep(espera)


@dataclass
class ResultadoEstructurado:
    success: bool
    data: Optional[BaseModel] = None
    error: Optional[str] = None


def generar_estructurado(prompt: str, schema: type[BaseModel], agente: str) -> ResultadoEstructurado:
    """
    Llamada genérica con structured output, para los agentes que
    no son el extractor (Pluma, Brújula). Mismo manejo de errores:
    nunca lanza excepciones hacia el agente, devuelve éxito o motivo.
    """
    try:
        response, _ = _generar_para(
            agente,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                # Sin herramientas: evita el aviso de "automatic function calling".
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return ResultadoEstructurado(success=True, data=schema.model_validate_json(response.text))
    except Exception as exc:
        return ResultadoEstructurado(success=False, error=f"Error llamando a Gemini {exc}")


def extract_job_info(cleaned_text: str) -> ExtractionResult:
    _get_client()  # falla temprano y claro si falta GEMINI_API_KEY
    prompt = PROMPT_TEMPLATE.format(texto=cleaned_text)

    try:
        response, _ = _generar_para(
            "lupa",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JobExtraction,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    except Exception as exc:  # errores de red/cuota de la API de Gemini
        return ExtractionResult(success=False, error=f"Error llamando a Gemini {exc}")

    try:
        parsed = JobExtraction.model_validate_json(response.text)
    except Exception as exc:  # por si acaso -- no debería pasar con response_schema
        return ExtractionResult(
            success=False,
            error=f"Gemini respondió pero no calzó con el schema esperado: {exc}",
        )

    return ExtractionResult(success=True, data=parsed)