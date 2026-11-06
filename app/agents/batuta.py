"""
batuta.py -- agente Batuta (orquestador)

Arma el grafo de LangGraph que encadena a los agentes:

    START -> lupa_leer -> lupa_extraer -> archivero -> balanza -> END
                 |              |
                 +--> END       +--> END   (si el agente marcó `terminado`)

Batuta no tiene lógica de negocio: solo decide el orden y cuándo
cortar. Más abajo está el segundo flujo (adaptar CV), con la pausa
del Preguntón.
"""

import sqlite3
import uuid
from typing import Optional

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents import archivero, balanza, eventos, imprenta, lupa, notario, pluma, pregunton
from app.agents.estado import CVState, OfertaState
from app.cv.cargador import RAIZ


def _siguiente_o_fin(siguiente: str):
    def decidir(state: OfertaState) -> str:
        return END if state.get("terminado") else siguiente
    return decidir


def construir_grafo():
    grafo = StateGraph(OfertaState)

    grafo.add_node("lupa_leer", lupa.leer_oferta)
    grafo.add_node("lupa_extraer", lupa.extraer)
    grafo.add_node("archivero", archivero.archivar)
    grafo.add_node("balanza", balanza.evaluar)

    grafo.add_edge(START, "lupa_leer")
    grafo.add_conditional_edges("lupa_leer", _siguiente_o_fin("lupa_extraer"))
    grafo.add_conditional_edges("lupa_extraer", _siguiente_o_fin("archivero"))
    grafo.add_edge("archivero", "balanza")
    grafo.add_edge("balanza", END)

    return grafo.compile()


_grafo = None


def analizar(
    url: Optional[str] = None,
    text: Optional[str] = None,
    origen: Optional[str] = None,
) -> OfertaState:
    """Corre el flujo completo para una oferta y devuelve el estado final."""
    global _grafo
    if _grafo is None:
        _grafo = construir_grafo()
    return _grafo.invoke({"url": url, "text": text, "origen": origen})


# ==============================================================
# Flujo 2: adaptar el CV a una oferta ya registrada
# ==============================================================
#
#   START -> balanza_preparar -> pregunton -> pluma_seleccionar
#         -> pluma_redactar -> pluma_validar -> notario_explicar
#                  ^                 |  |            -> notario_revisar
#                  +-- corregir -----+  |                  -> imprenta -> END
#                  (máx. MAX_INTENTOS)  +-- sin intentos: imprenta
#                                           con tus textos originales
#
# Hay dos pausas (interrupt): el Preguntón si tiene preguntas, y la
# revisión de Notario si la IA cambió textos. El estado se guarda con
# un checkpointer, así puedes responder otro día y el flujo sigue
# donde quedó, identificado por su thread_id.

RUTA_FLUJOS = RAIZ / "data" / "flujos.sqlite"


def construir_grafo_cv(checkpointer):
    grafo = StateGraph(CVState)

    grafo.add_node("balanza_preparar", balanza.preparar_para_cv)
    grafo.add_node("pregunton", pregunton.preguntar)
    grafo.add_node("pluma_seleccionar", pluma.seleccionar)
    grafo.add_node("pluma_redactar", pluma.redactar)
    grafo.add_node("pluma_validar", pluma.validar)
    grafo.add_node("notario_explicar", notario.explicar)
    grafo.add_node("notario_revisar", notario.revisar)
    grafo.add_node("imprenta", imprenta.imprimir)

    grafo.add_edge(START, "balanza_preparar")
    grafo.add_edge("balanza_preparar", "pregunton")
    grafo.add_edge("pregunton", "pluma_seleccionar")
    grafo.add_edge("pluma_seleccionar", "pluma_redactar")
    grafo.add_edge("pluma_redactar", "pluma_validar")
    grafo.add_conditional_edges(
        "pluma_validar", pluma.siguiente_tras_validar,
        {"notario": "notario_explicar", "imprenta": "imprenta", "pluma_redactar": "pluma_redactar"},
    )
    grafo.add_conditional_edges(
        "notario_explicar", notario.siguiente_tras_explicar,
        {"notario_revisar": "notario_revisar", "imprenta": "imprenta"},
    )
    grafo.add_edge("notario_revisar", "imprenta")
    grafo.add_edge("imprenta", END)

    return grafo.compile(checkpointer=checkpointer)


_grafo_cv = None


def _obtener_grafo_cv():
    global _grafo_cv
    if _grafo_cv is None:
        RUTA_FLUJOS.parent.mkdir(parents=True, exist_ok=True)
        conexion = sqlite3.connect(RUTA_FLUJOS, check_same_thread=False)
        _grafo_cv = construir_grafo_cv(SqliteSaver(conexion))
    return _grafo_cv


def _resumen(grafo, thread_id: str) -> dict:
    """Dónde quedó el flujo: esperando respuestas, esperando tu revisión o terminado."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = grafo.get_state(config)
    pendientes = [i.value for tarea in snapshot.tasks for i in tarea.interrupts]
    pausa = pendientes[0] if pendientes else {}
    # El Preguntón pausa con {"preguntas": [...]}; Notario con {"tipo": "revision", ...}.
    tipo = pausa.get("tipo", "preguntas") if pendientes else None
    return {
        "thread_id": thread_id,
        "esperando_respuestas": tipo == "preguntas",
        "preguntas": pausa.get("preguntas", []) if tipo == "preguntas" else [],
        "esperando_revision": tipo == "revision",
        "cambios": pausa.get("cambios", []) if tipo == "revision" else [],
        "estructura": pausa.get("estructura", []) if tipo == "revision" else [],
        "notario_error": pausa.get("notario_error") if tipo == "revision" else None,
        "estado": snapshot.values,
    }


def estado_cv(thread_id: str, grafo=None) -> dict:
    """Dónde quedó un flujo, sin avanzarlo (para validar lo que llega de la API)."""
    return _resumen(grafo or _obtener_grafo_cv(), thread_id)


def iniciar_cv(job_id: int, grafo=None) -> dict:
    grafo = grafo or _obtener_grafo_cv()
    thread_id = f"cv-{job_id}-{uuid.uuid4().hex[:8]}"
    grafo.invoke({"job_id": job_id}, {"configurable": {"thread_id": thread_id}})
    return _resumen(grafo, thread_id)


def responder_cv(thread_id: str, respuestas: list[dict], grafo=None) -> dict:
    grafo = grafo or _obtener_grafo_cv()
    grafo.invoke(Command(resume=respuestas), {"configurable": {"thread_id": thread_id}})
    return _resumen(grafo, thread_id)


def revisar_cv(thread_id: str, rechazados: list[str], grafo=None) -> dict:
    """Retoma la pausa de Notario: los cambios rechazados vuelven a tu texto original."""
    grafo = grafo or _obtener_grafo_cv()
    grafo.invoke(Command(resume={"rechazados": rechazados}), {"configurable": {"thread_id": thread_id}})
    return _resumen(grafo, thread_id)


# ==============================================================
# Versiones "en vivo": los mismos flujos, pero entregando un evento
# cada vez que un agente empieza o termina (ver eventos.py).
# ==============================================================

def analizar_en_vivo(url: Optional[str] = None, text: Optional[str] = None, origen: Optional[str] = None):
    global _grafo
    if _grafo is None:
        _grafo = construir_grafo()
    yield from eventos.transmitir(_grafo, {"url": url, "text": text, "origen": origen}, flujo="oferta")


def iniciar_cv_en_vivo(job_id: int, grafo=None):
    grafo = grafo or _obtener_grafo_cv()
    thread_id = f"cv-{job_id}-{uuid.uuid4().hex[:8]}"
    for ev in eventos.transmitir(grafo, {"job_id": job_id}, {"configurable": {"thread_id": thread_id}}, flujo="cv"):
        if ev["tipo"] != "_estado":
            yield ev
    yield {"tipo": "_resumen", "resumen": _resumen(grafo, thread_id)}


def responder_cv_en_vivo(thread_id: str, respuestas: list[dict], grafo=None):
    grafo = grafo or _obtener_grafo_cv()
    config = {"configurable": {"thread_id": thread_id}}
    for ev in eventos.transmitir(grafo, Command(resume=respuestas), config, flujo="cv"):
        if ev["tipo"] != "_estado":
            yield ev
    yield {"tipo": "_resumen", "resumen": _resumen(grafo, thread_id)}


def revisar_cv_en_vivo(thread_id: str, rechazados: list[str], grafo=None):
    yield from responder_cv_en_vivo(thread_id, {"rechazados": rechazados}, grafo=grafo)
