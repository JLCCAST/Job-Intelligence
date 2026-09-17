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
    Salida del endpoint.

    Se separan DOS cosas que antes no existían por separado:

    - `extraction_status`: ¿se logró obtener y analizar el texto?
    - `registration_status`: ¿se guardó en la BD, y por qué no?

    Una oferta puede extraerse perfecto (`success`) y aun así no
    guardarse, porque ya estaba cerrada o porque esa URL ya había
    sido registrada antes.
    """
    source: Literal["url", "manual_text"]
    extraction_status: Literal["success", "partial", "failed"]
    registration_status: Literal[
        "saved",          # se insertó un job nuevo
        "duplicate",      # esa URL ya estaba registrada -> job_id existente
        "offer_closed",   # la oferta ya no está disponible, no se guarda
        "not_attempted",  # no se llegó a intentar (falló antes)
    ] = "not_attempted"
    raw_length: int
    cleaned_text: Optional[str] = None
    error_detail: Optional[str] = None

    job_id: Optional[int] = None
    extraction: Optional["JobExtraction"] = None
    tecnologias_vinculadas: Optional[int] = None
    tecnologias_creadas: Optional[list[str]] = None
    tecnologias_para_revisar: Optional[list[str]] = None

    # --- Match Score (Fase 5) ---
    # `match_score` es None cuando la oferta no pide nada evaluable:
    # eso NO es un 0%, es "no hay información para comparar".
    match_score: Optional[float] = None
    cumple_ingles: Optional[bool] = None
    tecnologias_faltantes: Optional[list[str]] = None
    # Requisitos obligatorios que tienes pero en un nivel menor al
    # pedido: el score los suaviza, esta lista los deja visibles.
    requisitos_bajo_nivel: Optional[list[str]] = None


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
    company_name: str = Field(
        description=(
            "Nombre de la empresa que publica la oferta, tal como aparece "
            "en el texto. Si NO aparece de forma explícita, devolver "
            "exactamente 'no_especificado' -- no inferirlo ni inventarlo."
        )
    )
    source_name: Literal[
        "LinkedIn", "Indeed", "Computrabajo", "Bumeran",
        "Career Page", "Otro", "no_especificado",
    ] = Field(
        description=(
            "Portal donde se publicó la oferta, SOLO si el texto lo menciona "
            "explícitamente. Si no hay evidencia en el texto, "
            "'no_especificado'."
        )
    )
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

# JobExtraction se define más abajo que AnalyzeJobResponse, así que
# hay que resolver la referencia adelantada una vez que ya existe.
AnalyzeJobResponse.model_rebuild()
