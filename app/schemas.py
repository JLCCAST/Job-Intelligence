"""
Modelos para el endpoint POST /analyze-job y para la extracción de tecnologías con Gemini
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, HttpUrl, model_validator


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


class ExtractedTechnology(BaseModel):
    """
    Una tecnología detectada en la oferta, con su contexto replica 1 a 1 los campos de la tabla job_technology, 
    para que guardar esto en la BD después sea directo, sin transformación.
    """
    name: str = Field(description="Nombre de la tecnología tal como aparece en el texto")
    category: Literal[
        "Programming", "Database", "Cloud", "BI_Tool", "Automation_Tool",
        "Framework", "Methodology", "Soft_Skill", "Other",
    ]
    requirement_type: Literal["required", "preferred"]
    level: Literal["basico", "intermedio", "avanzado", "unspecified"]
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Qué tan seguro está el modelo de esta extracción, de 0 a 1",
    )
    evidence_text: str = Field(
        description="Frase textual de la oferta de donde se extrajo esto"
    )
 
 
class JobExtraction(BaseModel):
    job_title: str
    area: Literal[
        "BI", "Data_Analytics", "Data_Engineering", "Data_Science",
        "Software_Dev", "Cybersecurity", "Cloud", "IT_Support", "Other",
    ]
    english_level: Literal["basico", "intermedio", "avanzado", "no_especificado"]
    is_offer_available: bool = Field(
        description=(
            "False si el texto indica que la oferta ya está cerrada, "
            "cubierta, expirada o no disponible -- en ese caso "
            "technologies debe quedar vacío, no inventar requisitos."
        )
    )
    technologies: list[ExtractedTechnology]