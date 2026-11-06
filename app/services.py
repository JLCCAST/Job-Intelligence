"""
services.py

Capa de servicios: lo que la interfaz (la API de app/api.py, que usa
el frontend React) puede pedirle al sistema.
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
from app.cv import historial


def cambiar_estado(job_id: int, estado: str, nota: Optional[str] = None) -> None:
    """
    Cambia el estado de una oferta. Al pasar a "Postulada", la última
    versión del CV generada para esa oferta queda marcada como la enviada.
    """
    from app import consultas

    consultas.cambiar_estado(job_id, estado, nota)
    if estado == "Postulada":
        historial.marcar_enviado(job_id)


def versiones_cv(job_id: int) -> list[dict]:
    """Todas las versiones del CV generadas para una oferta, la más nueva primero."""
    return historial.versiones(job_id)


def _respuesta_analisis(estado: dict) -> AnalyzeJobResponse:
    # Las claves del estado se llaman igual que los campos de la
    # respuesta; las de control (url, text, terminado) se descartan.
    campos = AnalyzeJobResponse.model_fields
    return AnalyzeJobResponse(**{k: v for k, v in estado.items() if k in campos})


def analizar_oferta(url: Optional[str] = None, text: Optional[str] = None) -> AnalyzeJobResponse:
    return _respuesta_analisis(batuta.analizar(url=url, text=text))


# --------------------------------------------------------------
# Versiones en vivo (para la línea de agentes de la interfaz)
# --------------------------------------------------------------
# Entregan eventos {"tipo": "inicio" | "fin", "agente", ...} mientras
# los agentes trabajan, y al final {"tipo": "resultado", "datos": ...}
# con lo mismo que devolvería la versión normal. Batuta abre y cierra
# la transmisión: es quien coordina.

def _en_vivo(eventos_flujo, armar_resultado, accion: str):
    from time import perf_counter

    from app.agents import eventos

    inicio = perf_counter()
    yield {"tipo": "inicio", "nodo": "batuta", "agente": "batuta", "accion": accion}
    try:
        for ev in eventos_flujo:
            if ev["tipo"] in ("_estado", "_resumen"):
                resultado = armar_resultado(ev)
                continue
            yield ev
    except Exception as exc:  # la interfaz muestra el error en la línea de agentes
        yield {"tipo": "fin", "nodo": "batuta", "agente": "batuta", "estado": "error",
               "resumen": f"El flujo se detuvo: {str(exc)[:200]}", "ms": int((perf_counter() - inicio) * 1000)}
        yield {"tipo": "error", "mensaje": str(exc)[:300]}
        return
    ms = int((perf_counter() - inicio) * 1000)
    revision = isinstance(resultado, dict) and resultado.get("esperando_revision")
    pausa = isinstance(resultado, dict) and (resultado.get("esperando_respuestas") or revision)
    if revision:
        resumen = "Flujo en pausa: espero tu revisión de los cambios."
    elif pausa:
        resumen = "Flujo en pausa: espero tus respuestas."
    else:
        resumen = f"Flujo completo en {ms / 1000:.1f} s."
    eventos.registrar("batuta", resumen, "pausa" if pausa else "ok", "")
    yield {"tipo": "fin", "nodo": "batuta", "agente": "batuta", "estado": "pausa" if pausa else "ok", "resumen": resumen, "ms": ms}
    yield {"tipo": "resultado", "datos": resultado}


def analizar_oferta_en_vivo(url: Optional[str] = None, text: Optional[str] = None):
    return _en_vivo(
        batuta.analizar_en_vivo(url=url, text=text),
        lambda ev: _respuesta_analisis(ev["estado"]).model_dump(mode="json"),
        "Organizando el análisis de la oferta",
    )


def iniciar_adaptacion_cv_en_vivo(job_id: int):
    return _en_vivo(
        batuta.iniciar_cv_en_vivo(job_id),
        lambda ev: _resultado_cv(ev["resumen"]),
        "Organizando la adaptación de tu CV",
    )


def responder_preguntas_en_vivo(thread_id: str, respuestas: list[dict]):
    exigir_pausa(thread_id, "preguntas")
    return _en_vivo(
        batuta.responder_cv_en_vivo(thread_id, respuestas),
        lambda ev: _resultado_cv(ev["resumen"]),
        "Retomando la adaptación con tus respuestas",
    )


def revisar_cambios_en_vivo(thread_id: str, rechazados: list[str]):
    exigir_pausa(thread_id, "revision")
    return _en_vivo(
        batuta.revisar_cv_en_vivo(thread_id, rechazados),
        lambda ev: _resultado_cv(ev["resumen"]),
        "Retomando la adaptación con tu revisión",
    )


class FlujoNoEspera(Exception):
    """El flujo no está en la pausa que corresponde a lo que se envió."""


def exigir_pausa(thread_id: str, tipo: str) -> None:
    """
    Evita retomar una pausa con lo que no corresponde (respuestas del
    Preguntón cuando Notario espera tu revisión, o un flujo terminado).
    """
    r = batuta.estado_cv(thread_id)
    esperando = r["esperando_respuestas"] if tipo == "preguntas" else r["esperando_revision"]
    if not esperando:
        que = "respuestas" if tipo == "preguntas" else "una revisión de cambios"
        raise FlujoNoEspera(f"Este flujo no está esperando {que}. Vuelve a adaptar el CV.")


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
#   if r["esperando_revision"]:
#       mostrar r["cambios"] (con la explicación de Notario)
#       r = revisar_cambios(r["thread_id"], ids_rechazados)
#   r["ruta_cv"], r["ruta_brechas"]  -> los DOCX


def _resultado_cv(resumen: dict) -> dict:
    estado = resumen["estado"]
    return {
        "thread_id": resumen["thread_id"],
        "esperando_respuestas": resumen["esperando_respuestas"],
        "preguntas": resumen["preguntas"],
        # Revisión de Notario: cada cambio de la IA, con su explicación.
        "esperando_revision": resumen.get("esperando_revision", False),
        "cambios": resumen.get("cambios", []),
        "estructura": resumen.get("estructura", []),
        "notario_error": resumen.get("notario_error"),
        "ruta_cv": estado.get("ruta_cv"),
        "ruta_brechas": estado.get("ruta_brechas"),
        "usa_texto_de_pluma": bool(estado.get("redaccion")) and not estado.get("violaciones"),
        "avisos": estado.get("violaciones", []),
        "rechazados": estado.get("rechazados", []),
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
    from app.agents import eventos
    eventos.registrar(
        "brujula",
        f"Armé tu plan de estudio para {', '.join(i.tecnologia for i in plan.items)}." if plan
        else f"No pude armar el plan: {(error or '')[:120]}",
        "ok" if plan else "error", "rutina",
    )
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
    exigir_pausa(thread_id, "preguntas")
    return _resultado_cv(batuta.responder_cv(thread_id, respuestas))


def revisar_cambios(thread_id: str, rechazados: list[str]) -> dict:
    """
    `rechazados`: ids de los cambios de la IA que no quieres (vuelven a
    tu texto original). Los demás se aceptan. Retoma el flujo hasta
    Imprenta.
    """
    exigir_pausa(thread_id, "revision")
    return _resultado_cv(batuta.revisar_cv(thread_id, rechazados))
