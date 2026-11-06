"""
notario.py -- agente Notario

Tarea fija: dar fe de lo que la IA cambió en tu CV, antes de que lo
envíes. Dos nodos:

    explicar : (Python + Gemini) arma la lista de cambios entre tu CV
               base y el texto de Pluma (app/cv/cambios.py) y le pide a
               Gemini, en UNA sola llamada, que explique cada uno: qué
               cambió, por qué y qué requisito de la oferta atiende.
               Luego el código verifica lo que Gemini afirma.
    revisar  : (sin LLM) pausa el flujo hasta que aceptes o rechaces
               cada cambio. Imprenta solo usa lo que aceptaste.

Reglas de seguridad:
- Si Gemini falla o no hay cuota, el flujo sigue con el motivo
  calculado por código (nunca te quedas sin poder generar el CV).
- Notario no puede cambiar el texto: solo explica. Lo que dice se
  verifica: si cita un requisito que la oferta no pide, o que el texto
  nuevo no menciona, el cambio se marca con una alerta.
- Explicar y revisar son nodos separados a propósito: al retomar una
  pausa, LangGraph vuelve a correr el nodo que pausó; así no se gasta
  otra llamada a Gemini al responder.
"""

import re
from typing import Optional

from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.agents.estado import CVState
from app.cv.cambios import calcular_cambios, cambios_de_estructura
from app.cv.cargador import cargar_cv_base
from app.llm import generar_estructurado


class Explicacion(BaseModel):
    id: str = Field(description="El mismo id del cambio que se te entregó")
    motivo: str = Field(description="Una o dos frases: qué cambió y por qué, en segunda persona ('tu bullet...')")
    requisitos: list[str] = Field(
        description="Nombres EXACTOS de requisitos de la oferta que este cambio atiende; vacío si ninguno"
    )
    revisar: Optional[str] = Field(
        default=None,
        description=(
            "Solo si el cambio podría exagerar tu participación, cambiar el sentido o sonar forzado: "
            "una frase con qué revisar. Si está bien, null."
        ),
    )


class ExplicacionCambios(BaseModel):
    explicaciones: list[Explicacion]


PROMPT_NOTARIO = """\
Eres un revisor de CVs. Otra IA reescribió partes del CV de un candidato
para una oferta laboral. Tu tarea es EXPLICARLE al candidato cada cambio,
para que decida si lo acepta. No reescribas nada.

Para cada cambio responde:
- motivo: qué cambió y por qué ayuda para esta oferta, en 1 o 2 frases
  claras, hablándole al candidato ("Agregué...", "Resumí...").
- requisitos: los requisitos de la oferta que el cambio atiende, escritos
  EXACTAMENTE como en la lista de requisitos. Vacío si no atiende ninguno.
  No cites un requisito que el texto nuevo no mencione.
- revisar: solo si el texto nuevo podría exagerar lo que hizo el
  candidato (por ejemplo, de "apoyé en" a "lideré"), cambiar el sentido
  del original o sonar forzado. Si no, null.

Sé honesto: si un cambio solo reordena palabras, dilo.

OFERTA
Puesto: {puesto}
Requisitos: {requisitos}

CAMBIOS
{cambios}"""


def armar_prompt(oferta: dict, cambios: list[dict]) -> str:
    bloques = [
        f"[id={c['id']}] ({c['item']})\n  ORIGINAL: {c['original']}\n  NUEVO: {c['nuevo']}"
        for c in cambios
    ]
    return PROMPT_NOTARIO.format(
        puesto=oferta["puesto"],
        requisitos=", ".join(r["nombre"] for r in oferta["requisitos"]) or "(sin requisitos)",
        cambios="\n\n".join(bloques),
    )


def _aparece(termino: str, texto: str) -> bool:
    patron = r"(?<![\w])" + re.escape(termino) + r"(?![\w])"
    return re.search(patron, texto, flags=re.IGNORECASE) is not None


def aplicar_explicaciones(cambios: list[dict], explicaciones: list[dict], oferta: dict) -> list[dict]:
    """
    Pone la explicación de Notario en cada cambio y verifica lo que
    afirma. Un cambio sin explicación conserva el motivo calculado.
    """
    por_id = {e["id"]: e for e in explicaciones}
    nombres_oferta = {r["nombre"].strip().lower(): r["nombre"] for r in oferta["requisitos"]}
    resultado = []
    for c in cambios:
        e = por_id.get(c["id"])
        if not e or not (e.get("motivo") or "").strip():
            resultado.append(c)
            continue
        alertas = []
        citados = []
        for req in e.get("requisitos") or []:
            canonico = nombres_oferta.get(req.strip().lower())
            if canonico is None:
                alertas.append(f"El motivo cita «{req}», pero la oferta no lo pide.")
            elif not _aparece(canonico, c["nuevo"]):
                alertas.append(f"El motivo cita «{canonico}», pero el texto nuevo no lo menciona.")
            else:
                citados.append(canonico)
        resultado.append({
            **c,
            "motivo": e["motivo"].strip(),
            "motivo_de": "notario",
            "requisitos": citados,
            "atencion": (e.get("revisar") or "").strip() or None,
            "alerta": " ".join(alertas) or None,
        })
    return resultado


def explicar(state: CVState) -> CVState:
    cv = cargar_cv_base()
    cambios = calcular_cambios(
        cv, state["oferta"], state["seleccion"], state.get("redaccion"),
        state.get("respuestas_confirmadas", []),
    )
    estructura = cambios_de_estructura(cv, state["seleccion"])
    if not cambios:
        return {"cambios": [], "estructura_cv": estructura, "notario_error": None}

    resultado = generar_estructurado(armar_prompt(state["oferta"], cambios), ExplicacionCambios, agente="notario")
    if not resultado.success:
        # Sin Gemini: quedan los motivos calculados. El flujo sigue.
        return {"cambios": cambios, "estructura_cv": estructura, "notario_error": resultado.error}

    explicaciones = [e.model_dump() for e in resultado.data.explicaciones]
    return {
        "cambios": aplicar_explicaciones(cambios, explicaciones, state["oferta"]),
        "estructura_cv": estructura,
        "notario_error": None,
    }


def siguiente_tras_explicar(state: CVState) -> str:
    # Si Pluma no cambió ningún texto, no hay nada que revisar.
    return "notario_revisar" if state.get("cambios") else "imprenta"


def revisar(state: CVState) -> CVState:
    cambios = state.get("cambios") or []
    decision = interrupt({
        "tipo": "revision",
        "cambios": cambios,
        "estructura": state.get("estructura_cv", []),
        "notario_error": state.get("notario_error"),
    })
    ids = {c["id"] for c in cambios}
    rechazados = [i for i in (decision or {}).get("rechazados", []) if i in ids]
    return {"rechazados": rechazados}
