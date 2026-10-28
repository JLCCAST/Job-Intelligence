"""
estado.py

Estado compartido que viaja por el grafo de Batuta. Cada agente
lee lo que necesita y devuelve SOLO las claves que cambia; LangGraph
las mezcla en el estado.

Las claves se llaman igual que los campos de AnalyzeJobResponse a
propósito: así la capa de servicios arma la respuesta sin traducir
nombres.
"""

from typing import Optional, TypedDict

from app.schemas import JobExtraction


class OfertaState(TypedDict, total=False):
    # --- Entrada ---
    url: Optional[str]
    text: Optional[str]
    origen: Optional[str]  # "api" cuando la oferta la trae Sabueso

    # --- Control de flujo ---
    # True cuando un agente decide que el flujo termina ahí
    # (duplicado, scraping fallido, Gemini caído, oferta cerrada).
    terminado: bool

    # --- Lupa ---
    source: str  # "url" | "manual_text"
    raw_length: int
    cleaned_text: Optional[str]
    extraction_status: str
    extraction: Optional[JobExtraction]

    # --- Archivero ---
    registration_status: str
    job_id: Optional[int]
    tecnologias_vinculadas: Optional[int]
    tecnologias_creadas: Optional[list[str]]
    tecnologias_para_revisar: Optional[list[str]]

    # --- Balanza ---
    match_score: Optional[float]
    cumple_ingles: Optional[bool]
    tecnologias_faltantes: Optional[list[str]]
    requisitos_bajo_nivel: Optional[list[str]]

    error_detail: Optional[str]


class CVState(TypedDict, total=False):
    """
    Estado del flujo de adaptación de CV. Solo tipos simples (dict,
    list, str): este estado se guarda en SQLite mientras el flujo
    espera tus respuestas, y así se puede retomar otro día.
    """
    job_id: int
    oferta: dict                        # repository.leer_oferta_para_cv

    # --- Preguntón ---
    preguntas: list[dict]
    respuestas_confirmadas: list[dict]  # Respuesta.model_dump() con la_tengo=True

    # --- Pluma ---
    seleccion: dict                     # qué experiencias/proyectos van y en qué orden
    redaccion: Optional[dict]           # RedaccionCV.model_dump()
    violaciones: list[str]              # lo que encontró el validador
    historial_violaciones: list[list[str]]  # una lista por intento
    intentos: int
    error_detail: Optional[str]

    # --- Imprenta ---
    ruta_cv: Optional[str]
    ruta_brechas: Optional[str]
