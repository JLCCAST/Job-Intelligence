"""
pregunton.py -- agente Preguntón

Tarea fija: antes de que Pluma escriba, preguntarte por cada
requisito de la oferta que NO aparece ni en tu perfil (user_skill),
ni en tu CV base, ni en respuestas anteriores. El flujo se PAUSA
(interrupt de LangGraph) hasta que respondas.

Las preguntas se arman con una plantilla, sin LLM: son siempre la
misma pregunta ("¿lo has usado? ¿dónde? ¿qué nivel?") y una
plantilla no se equivoca ni gasta cuota.
"""

from langgraph.types import interrupt

from app.agents.estado import CVState
from app.cv.cargador import cargar_cv_base
from app.cv.respuestas import Respuesta, cargar_respuestas, guardar_respuestas

# El inglés ya está en la sección de idiomas del CV base; no se pregunta.
NO_PREGUNTAR = {"inglés", "ingles", "english"}

TIPO_LEGIBLE = {"required": "obligatorio", "preferred": "deseable"}


def armar_preguntas(requisitos: list[dict], skills_cv: set[str], ya_respondidas: set[str]) -> list[dict]:
    preguntas = []
    for req in requisitos:
        nombre = req["nombre"]
        clave = nombre.strip().lower()
        if (
            req["nivel_usuario"] is not None
            or clave in NO_PREGUNTAR
            or clave in skills_cv
            or clave in ya_respondidas
        ):
            continue

        nivel = req.get("nivel_pedido")
        nivel_txt = f" (nivel {nivel})" if nivel and nivel != "unspecified" else ""
        preguntas.append({
            "tecnologia": nombre,
            "requirement_type": req["requirement_type"],
            "texto": (
                f"La oferta pide {nombre} como requisito "
                f"{TIPO_LEGIBLE.get(req['requirement_type'], req['requirement_type'])}{nivel_txt}. "
                "¿Lo has usado? Si es así, ¿dónde (proyecto, trabajo o curso) y con qué nivel?"
            ),
        })
    return preguntas


def preguntar(state: CVState) -> CVState:
    cv = cargar_cv_base()
    respuestas_previas = cargar_respuestas()

    preguntas = armar_preguntas(
        state["oferta"]["requisitos"],
        skills_cv=cv.skills_declaradas(),
        ya_respondidas=set(respuestas_previas),
    )

    if preguntas:
        # Pausa: el flujo se guarda y espera. Al reanudar con
        # Command(resume=[...]) la lista de respuestas llega aquí.
        crudas = interrupt({"preguntas": preguntas})
        nuevas = [Respuesta.model_validate(r) for r in crudas]
        guardar_respuestas(nuevas)
        respuestas_previas = cargar_respuestas()

    # Solo viaja lo relevante para ESTA oferta y que confirmaste tener.
    nombres_oferta = {r["nombre"].strip().lower() for r in state["oferta"]["requisitos"]}
    confirmadas = [
        r.model_dump() for clave, r in respuestas_previas.items()
        if r.la_tengo and clave in nombres_oferta
    ]
    return {"preguntas": preguntas, "respuestas_confirmadas": confirmadas}
