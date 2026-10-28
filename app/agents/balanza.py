"""
balanza.py -- agente Balanza

Tarea fija: pesar tu perfil (user_skill) contra los requisitos de
la oferta ya guardada y devolver el Match Score y las brechas.
100% determinístico: el LLM no participa.
"""

from app.repository import calcular_y_guardar_match_score, leer_oferta_para_cv
from app.agents.estado import OfertaState


def evaluar(state: OfertaState) -> OfertaState:
    # Se calcula DESPUÉS del Archivero porque lee job_technology,
    # que recién existe una vez guardada la oferta.
    score = calcular_y_guardar_match_score(state["job_id"])

    return {
        "match_score": score.score,
        "cumple_ingles": score.cumple_ingles,
        "tecnologias_faltantes": score.faltantes,
        "requisitos_bajo_nivel": score.requisitos_bajo_nivel,
    }


def preparar_para_cv(state) -> dict:
    """
    Primer paso del flujo de CV: el desglose del Match Score
    requisito por requisito (qué cumples, qué te falta, qué tienes
    en un nivel menor), que usan el Preguntón, Pluma e Imprenta.
    """
    return {"oferta": leer_oferta_para_cv(state["job_id"])}
