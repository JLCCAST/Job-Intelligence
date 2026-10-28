"""
archivero.py -- agente Archivero

Tarea fija: decidir la fuente de la oferta y guardarla en la BD,
normalizando empresa y tecnologías contra el catálogo (alias,
nombre canónico o creación con `necesita_revision`). Sin LLM.
"""

from app.repository import insert_job_with_technologies
from app.source_resolver import resolver_source
from app.agents.estado import OfertaState


def archivar(state: OfertaState) -> OfertaState:
    extraction = state["extraction"]
    url = state.get("url")

    # Con URL manda el dominio (determinístico); sin URL, lo que
    # haya inferido Gemini del texto.
    source_name = resolver_source(url=url, source_name_gemini=extraction.source_name)

    resultado = insert_job_with_technologies(
        extraction=extraction,
        source_name=source_name,
        url=url,
        descripcion_raw=None,
        descripcion_limpia=state["cleaned_text"],
    )

    return {
        "registration_status": "saved",
        "job_id": resultado.job_id,
        "tecnologias_vinculadas": resultado.tecnologias_vinculadas,
        "tecnologias_creadas": resultado.tecnologias_creadas,
        "tecnologias_para_revisar": resultado.tecnologias_para_revisar,
    }
