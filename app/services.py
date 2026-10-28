"""
services.py

Capa de servicios: lo que la interfaz (FastAPI hoy, Streamlit
después, un frontend HTML más adelante) puede pedirle al sistema.
Ninguna interfaz llama directo a los agentes: siempre pasa por acá,
así cambiar de interfaz no toca la lógica.
"""

from typing import Optional

from app.agents import batuta
from app.schemas import AnalyzeJobResponse

# Consultas simples (listar, cambiar estado, perfil, catálogo): no
# pasan por agentes, así que se exponen tal cual desde aquí para que
# la interfaz importe SOLO de services.
from app.consultas import (  # noqa: F401
    aprobar_tecnologia,
    cambiar_estado,
    demanda_tecnologias,
    guardar_habilidad,
    historial_estados,
    listar_estados,
    listar_mi_perfil,
    listar_ofertas,
    tecnologias_para_revisar,
)
from app.cv.cargador import CVBaseNoEncontrado, cargar_cv_base  # noqa: F401
from app.cv.respuestas import cargar_respuestas  # noqa: F401


def analizar_oferta(url: Optional[str] = None, text: Optional[str] = None) -> AnalyzeJobResponse:
    estado = batuta.analizar(url=url, text=text)

    # Las claves del estado se llaman igual que los campos de la
    # respuesta; las de control (url, text, terminado) se descartan.
    campos = AnalyzeJobResponse.model_fields
    return AnalyzeJobResponse(**{k: v for k, v in estado.items() if k in campos})


# --------------------------------------------------------------
# Adaptar CV (Preguntón -> Pluma -> Imprenta)
# --------------------------------------------------------------
#
# Uso típico desde una interfaz:
#
#   r = iniciar_adaptacion_cv(job_id)
#   if r["esperando_respuestas"]:
#       mostrar r["preguntas"], juntar respuestas del usuario
#       r = responder_preguntas(r["thread_id"], respuestas)
#   r["ruta_cv"], r["ruta_brechas"]  -> los DOCX


def _resultado_cv(resumen: dict) -> dict:
    estado = resumen["estado"]
    return {
        "thread_id": resumen["thread_id"],
        "esperando_respuestas": resumen["esperando_respuestas"],
        "preguntas": resumen["preguntas"],
        "ruta_cv": estado.get("ruta_cv"),
        "ruta_brechas": estado.get("ruta_brechas"),
        "usa_texto_de_pluma": bool(estado.get("redaccion")) and not estado.get("violaciones"),
        "avisos": estado.get("violaciones", []),
    }


def iniciar_adaptacion_cv(job_id: int) -> dict:
    return _resultado_cv(batuta.iniciar_cv(job_id))


def buscar_ofertas_nuevas() -> dict:
    """Corre Sabueso ahora mismo (lo mismo que hace la rutina diaria)."""
    from dataclasses import asdict

    from app.agents import sabueso
    return asdict(sabueso.ejecutar())


def _calcular_brujula():
    from app.agents import brujula
    from app.consultas import requisitos_para_brujula

    filas = requisitos_para_brujula()
    try:
        cv = cargar_cv_base()
        skills_cv, skills_base = cv.skills_declaradas(), cv.skills_con_formato()
    except CVBaseNoEncontrado:
        skills_cv, skills_base = set(), []
    confirmadas = {clave: r.nivel for clave, r in cargar_respuestas().items() if r.la_tengo}
    prioridades = brujula.calcular_prioridades(filas, skills_cv, confirmadas)
    return prioridades, len({f["job_id"] for f in filas}), skills_base


def prioridades_estudio() -> dict:
    """Ranking de Brújula: qué estudiar primero (sin LLM)."""
    from dataclasses import asdict

    prioridades, total, _ = _calcular_brujula()
    return {"total_ofertas": total, "prioridades": [asdict(p) for p in prioridades]}


def generar_plan_estudio() -> dict:
    """Pide a Gemini el plan para el top de Brújula y lo guarda. {"plan": ..., "error": ...}"""
    from app.agents import brujula

    prioridades, _, skills_base = _calcular_brujula()
    top = prioridades[:brujula.TOP_PLAN]
    plan, error = brujula.generar_plan(top, skills_base)
    if plan is not None:
        brujula.guardar_plan(plan, top)
    return {"plan": brujula.cargar_plan() if plan else None, "error": error}


def cargar_plan_estudio() -> Optional[dict]:
    from app.agents import brujula
    return brujula.cargar_plan()


def generar_informe_brujula() -> str:
    from app.agents import brujula

    prioridades, total, _ = _calcular_brujula()
    return str(brujula.generar_informe(prioridades, total, brujula.cargar_plan()))


def resumen_centinela() -> dict:
    from app.agents import centinela
    return centinela.armar_resumen()


def responder_preguntas(thread_id: str, respuestas: list[dict]) -> dict:
    """
    `respuestas`: una por pregunta, con la forma de app.cv.respuestas.Respuesta:
        {"tecnologia": "Airflow", "la_tengo": False}
        {"tecnologia": "dbt", "la_tengo": True, "nivel": "basico",
         "donde": "Curso X", "detalle": "modelos incrementales"}
    """
    return _resultado_cv(batuta.responder_cv(thread_id, respuestas))
