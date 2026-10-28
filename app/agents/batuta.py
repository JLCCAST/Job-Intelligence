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

from app.agents import archivero, balanza, imprenta, lupa, pluma, pregunton
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
#         -> pluma_redactar -> pluma_validar -> imprenta -> END
#                  ^                 |
#                  +-- corregir -----+   (máx. MAX_INTENTOS)
#
# El Preguntón PAUSA el flujo (interrupt) si tiene preguntas. El
# estado se guarda con un checkpointer, así puedes responder otro
# día y el flujo sigue donde quedó, identificado por su thread_id.

RUTA_FLUJOS = RAIZ / "data" / "flujos.sqlite"


def construir_grafo_cv(checkpointer):
    grafo = StateGraph(CVState)

    grafo.add_node("balanza_preparar", balanza.preparar_para_cv)
    grafo.add_node("pregunton", pregunton.preguntar)
    grafo.add_node("pluma_seleccionar", pluma.seleccionar)
    grafo.add_node("pluma_redactar", pluma.redactar)
    grafo.add_node("pluma_validar", pluma.validar)
    grafo.add_node("imprenta", imprenta.imprimir)

    grafo.add_edge(START, "balanza_preparar")
    grafo.add_edge("balanza_preparar", "pregunton")
    grafo.add_edge("pregunton", "pluma_seleccionar")
    grafo.add_edge("pluma_seleccionar", "pluma_redactar")
    grafo.add_edge("pluma_redactar", "pluma_validar")
    grafo.add_conditional_edges("pluma_validar", pluma.siguiente_tras_validar)
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
    """Dónde quedó el flujo: esperando respuestas o terminado."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = grafo.get_state(config)
    pendientes = [i.value for tarea in snapshot.tasks for i in tarea.interrupts]
    return {
        "thread_id": thread_id,
        "esperando_respuestas": bool(pendientes),
        "preguntas": pendientes[0]["preguntas"] if pendientes else [],
        "estado": snapshot.values,
    }


def iniciar_cv(job_id: int, grafo=None) -> dict:
    grafo = grafo or _obtener_grafo_cv()
    thread_id = f"cv-{job_id}-{uuid.uuid4().hex[:8]}"
    grafo.invoke({"job_id": job_id}, {"configurable": {"thread_id": thread_id}})
    return _resumen(grafo, thread_id)


def responder_cv(thread_id: str, respuestas: list[dict], grafo=None) -> dict:
    grafo = grafo or _obtener_grafo_cv()
    grafo.invoke(Command(resume=respuestas), {"configurable": {"thread_id": thread_id}})
    return _resumen(grafo, thread_id)
