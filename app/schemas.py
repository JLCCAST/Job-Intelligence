"""
Modelos para el endpoint POST /analyze-job.
Por ahora solo extrae y limpia el contenido.
"""

from typing import Literal, Optional
from pydantic import BaseModel, HttpUrl, model_validator


class AnalyzeJobRequest(BaseModel):
    """
    Entrada del endpoint. El usuario debe enviar `url` (Opción A) O `text` (Opción B, fallback manual),
    pero al menos uno es obligatorio.
    """
    url: Optional[HttpUrl] = None
    text: Optional[str] = None

    @model_validator(mode="after")
    def al_menos_uno_presente(self) -> "AnalyzeJobRequest":
        if not self.url and not self.text:
            raise ValueError(
                "Debes enviar 'url' o 'text' (al menos uno de los dos)."
            )
        return self


class AnalyzeJobResponse(BaseModel):
    """
    Salida del endpoint por ahora es solo el resultado de la
    extracción + limpieza.
    """
    source: Literal["url", "manual_text"]
    extraction_status: Literal["success", "partial", "failed"]
    raw_length: int
    cleaned_text: Optional[str] = None
    error_detail: Optional[str] = None