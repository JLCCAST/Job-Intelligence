"""
gemini.py

Responsabilidad única: recibir texto limpio (ya procesado por
cleaner.py) y devolver una extracción estructurada usando Gemini
con structured output (response_schema). No decide qué hacer con
el resultado -- eso lo maneja quien llame a esta función.
"""

import os
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv

from app.schemas import JobExtraction

load_dotenv()  # lee el .env y carga GEMINI_API_KEY como variable de entorno

MODEL_NAME = "gemini-3.6-flash"  # gemini-2.5-flash fue discontinuado (jul 2026);
# no usamos un modelo "Pro": cuota diaria gratuita mucho más baja (Fase 1)

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

Texto de la oferta:
---
{texto}
---
"""


def extract_job_info(cleaned_text: str) -> ExtractionResult:
    client = _get_client()
    prompt = PROMPT_TEMPLATE.format(texto=cleaned_text)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=JobExtraction,
            ),
        )
    except Exception as exc:  # errores de red/cuota de la API de Gemini
        return ExtractionResult(success=False, error=f"Error llamando a Gemini: {exc}")

    try:
        parsed = JobExtraction.model_validate_json(response.text)
    except Exception as exc:  # por si acaso -- no debería pasar con response_schema
        return ExtractionResult(
            success=False,
            error=f"Gemini respondió pero no calzó con el schema esperado: {exc}",
        )

    return ExtractionResult(success=True, data=parsed)