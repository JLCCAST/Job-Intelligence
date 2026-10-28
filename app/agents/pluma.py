"""
pluma.py -- agente Pluma

Tarea fija: adaptar tu CV a una oferta SIN inventar nada. Tres nodos:

    seleccionar : (Python) qué proyectos van y en qué orden, según
                  cuántos requisitos de la oferta tocan.
    redactar    : (Gemini) reescribe perfil y bullets con el
                  vocabulario de la oferta. Solo recibe índices: no
                  puede cambiar nombres, empresas ni fechas.
    validar     : (Python) revisa que no aparezca ninguna tecnología
                  ni cifra que no esté en tu CV base o que no hayas
                  confirmado en el Preguntón. Si falla, Batuta
                  devuelve el texto a `redactar` con el motivo.
"""

import re
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from app.agents.estado import CVState
from app.cv.cargador import cargar_cv_base
from app.cv.modelo import CVBase
from app.gemini import generar_estructurado

MAX_PROYECTOS = 3
MAX_LOGROS_POR_ITEM = 4
MAX_INTENTOS = 3  # 1 redacción + 2 correcciones

PESO_TIPO = {"required": 1.0, "preferred": 0.5}
NO_ES_TECNOLOGIA = {"inglés", "ingles", "english"}


# --------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------

def _aparece(termino: str, texto: str) -> bool:
    """¿`termino` aparece como palabra completa? ("SQL" no calza con "NoSQL")."""
    patron = r"(?<![\w])" + re.escape(termino) + r"(?![\w])"
    return re.search(patron, texto, flags=re.IGNORECASE) is not None


def _terminos_oferta(oferta: dict) -> list[tuple[str, float]]:
    return [
        (r["nombre"], PESO_TIPO.get(r["requirement_type"], 0.5))
        for r in oferta["requisitos"]
        if r["nombre"].strip().lower() not in NO_ES_TECNOLOGIA
    ]


def _relevancia(texto: str, terminos: list[tuple[str, float]]) -> float:
    return sum(peso for nombre, peso in terminos if _aparece(nombre, texto))


def _cifras(texto: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", texto))


# --------------------------------------------------------------
# Nodo 1: seleccionar (sin LLM)
# --------------------------------------------------------------

def _ordenar_logros(logros: list[str], terminos) -> list[int]:
    # sorted es estable: a igual relevancia se respeta tu orden original.
    orden = sorted(range(len(logros)), key=lambda i: -_relevancia(logros[i], terminos))
    return orden[:MAX_LOGROS_POR_ITEM]


def calcular_seleccion(cv: CVBase, oferta: dict) -> dict:
    terminos = _terminos_oferta(oferta)

    # La experiencia laboral va completa y en orden cronológico; solo
    # se reordenan sus bullets.
    experiencia = [
        {"indice": i, "logros": _ordenar_logros(e.logros, terminos)}
        for i, e in enumerate(cv.experiencia)
    ]

    def texto_proyecto(p) -> str:
        return " ".join([p.nombre, *p.stack, *p.logros])

    ranking = sorted(
        range(len(cv.proyectos)),
        key=lambda i: -_relevancia(texto_proyecto(cv.proyectos[i]), terminos),
    )
    proyectos = [
        {"indice": i, "logros": _ordenar_logros(cv.proyectos[i].logros, terminos)}
        for i in ranking[:MAX_PROYECTOS]
    ]
    return {"experiencia": experiencia, "proyectos": proyectos}


def seleccionar(state: CVState) -> CVState:
    cv = cargar_cv_base()
    return {
        "seleccion": calcular_seleccion(cv, state["oferta"]),
        "intentos": 0,
        "violaciones": [],
        "historial_violaciones": [],
    }


# --------------------------------------------------------------
# Nodo 2: redactar (Gemini)
# --------------------------------------------------------------

class ItemRedactado(BaseModel):
    indice: int = Field(description="El mismo índice que se te entregó; no lo cambies")
    logros: list[str] = Field(description="Los bullets reescritos, en el mismo orden y cantidad")


class RedaccionCV(BaseModel):
    perfil: str = Field(description="Resumen profesional de 3 a 5 líneas, en primera persona implícita")
    experiencia: list[ItemRedactado]
    proyectos: list[ItemRedactado]
    habilidades_destacadas: list[str] = Field(
        description="Hasta 8 habilidades de la lista permitida, las más relevantes para la oferta"
    )


PROMPT_REDACCION = """\
Eres un redactor de CVs. Adapta el CV de un candidato a una oferta laboral.

REGLAS ESTRICTAS (si rompes una, el texto se rechaza):
1. No inventes experiencia, tecnologías, herramientas, cifras ni logros.
   Solo puedes reformular lo que está en el material del candidato.
2. Solo puedes mencionar tecnologías de esta lista permitida:
   {permitidas}
3. No agregues cifras (porcentajes, cantidades, años) que no estén en el
   material original.
4. Mantén el mismo `indice` y la misma cantidad de bullets por ítem.
5. Usa el vocabulario de la oferta cuando describa lo MISMO que hizo el
   candidato. Empieza cada bullet con un verbo en pasado.
6. Escribe en español, claro y sin adornos ("apasionado", "experto").
7. Respeta el grado de participación original: si dice "apoyo en" o
   "participación en", no lo conviertas en algo que hizo solo ("revisé",
   "lideré"). Usa "apoyé en", "participé en", "colaboré en".
8. Escribe los nombres de herramientas tal como aparecen en la lista
   permitida ("Power BI", "SQL Server"). Los conceptos generales
   ("calidad de datos", "geolocalización", "dashboards") van en
   minúscula a mitad de frase, como en español normal.

OFERTA
Puesto: {puesto}
Empresa: {empresa}
Área: {area}
Requisitos: {requisitos}

PERFIL ORIGINAL DEL CANDIDATO
{perfil}

EXPERIENCIA (reescribe estos bullets)
{experiencia}

PROYECTOS (reescribe estos bullets)
{proyectos}

INFORMACIÓN CONFIRMADA POR EL CANDIDATO (puedes usarla)
{confirmadas}
{correcciones}"""


def _bloque_items(items_cv, seleccion_items) -> str:
    lineas = []
    for sel in seleccion_items:
        item = items_cv[sel["indice"]]
        titulo = getattr(item, "nombre", None) or f"{item.cargo} en {item.empresa}"
        lineas.append(f"[indice={sel['indice']}] {titulo}")
        lineas += [f"  - {item.logros[i]}" for i in sel["logros"]]
    return "\n".join(lineas) or "(ninguno)"


def armar_prompt(cv: CVBase, state: CVState) -> str:
    oferta = state["oferta"]
    confirmadas = "\n".join(
        f"- {r['tecnologia']} (nivel {r.get('nivel') or 'no indicado'}): "
        f"{r.get('donde') or ''} {r.get('detalle') or ''}".rstrip()
        for r in state.get("respuestas_confirmadas", [])
    ) or "(ninguna)"

    correcciones = ""
    if state.get("violaciones"):
        correcciones = (
            "\nTU VERSIÓN ANTERIOR FUE RECHAZADA. Corrige esto:\n"
            + "\n".join(f"- {v}" for v in state["violaciones"])
        )

    return PROMPT_REDACCION.format(
        permitidas=", ".join(
            cv.skills_con_formato()
            + [r["tecnologia"] for r in state.get("respuestas_confirmadas", [])]
        ),
        puesto=oferta["puesto"],
        empresa=oferta.get("empresa") or "no especificada",
        area=oferta.get("area") or "no especificada",
        requisitos=", ".join(
            f"{r['nombre']} ({r['requirement_type']})" for r in oferta["requisitos"]
        ),
        perfil=cv.perfil,
        experiencia=_bloque_items(cv.experiencia, state["seleccion"]["experiencia"]),
        proyectos=_bloque_items(cv.proyectos, state["seleccion"]["proyectos"]),
        confirmadas=confirmadas,
        correcciones=correcciones,
    )


def skills_permitidas(cv: CVBase, respuestas_confirmadas: list[dict]) -> set[str]:
    return cv.skills_declaradas() | {r["tecnologia"].strip().lower() for r in respuestas_confirmadas}


def redactar(state: CVState) -> CVState:
    cv = cargar_cv_base()
    resultado = generar_estructurado(armar_prompt(cv, state), RedaccionCV, agente="pluma")

    if not resultado.success:
        return {"redaccion": None, "error_detail": resultado.error}
    return {"redaccion": resultado.data.model_dump(), "error_detail": None}


# --------------------------------------------------------------
# Nodo 3: validar (sin LLM)
# --------------------------------------------------------------

def encontrar_violaciones(
    cv: CVBase,
    oferta: dict,
    seleccion: dict,
    redaccion: Optional[dict],
    respuestas_confirmadas: list[dict],
) -> list[str]:
    if redaccion is None:
        return ["No hubo redacción (falló la llamada a Gemini)."]

    permitidas = skills_permitidas(cv, respuestas_confirmadas)
    violaciones = []

    # 1. Estructura: los mismos ítems que se pidieron.
    for seccion in ("experiencia", "proyectos"):
        pedidos = {s["indice"] for s in seleccion[seccion]}
        recibidos = {i["indice"] for i in redaccion[seccion]}
        if pedidos != recibidos:
            violaciones.append(
                f"En {seccion} se esperaban los índices {sorted(pedidos)} y llegaron {sorted(recibidos)}."
            )

    texto = " ".join(
        [redaccion["perfil"]]
        + [l for s in ("experiencia", "proyectos") for i in redaccion[s] for l in i["logros"]]
    )

    # 2. Tecnologías que la oferta pide y el candidato NO tiene.
    for req in oferta["requisitos"]:
        nombre = req["nombre"]
        clave = nombre.strip().lower()
        if clave in NO_ES_TECNOLOGIA or clave in permitidas:
            continue
        if _aparece(nombre, texto):
            violaciones.append(f"Menciona {nombre}, que no está en el CV ni fue confirmado.")

    for h in redaccion["habilidades_destacadas"]:
        if h.strip().lower() not in permitidas:
            violaciones.append(f"La habilidad destacada '{h}' no está en la lista permitida.")

    # 3. Cifras nuevas (métricas inventadas).
    texto_original = yaml.safe_dump(cv.model_dump(), allow_unicode=True)
    texto_original += " ".join(str(r) for r in respuestas_confirmadas)
    for cifra in sorted(_cifras(texto) - _cifras(texto_original)):
        violaciones.append(f"Usa la cifra {cifra}, que no aparece en el material original.")

    return violaciones


def validar(state: CVState) -> CVState:
    cv = cargar_cv_base()
    violaciones = encontrar_violaciones(
        cv, state["oferta"], state["seleccion"], state.get("redaccion"),
        state.get("respuestas_confirmadas", []),
    )
    if state.get("redaccion") is None and state.get("error_detail"):
        violaciones = [f"{violaciones[0]} {state['error_detail']}"]
    return {
        "violaciones": violaciones,
        "intentos": state.get("intentos", 0) + 1,
        # Queda registro de por qué se rechazó cada intento.
        "historial_violaciones": state.get("historial_violaciones", []) + [violaciones],
    }


def siguiente_tras_validar(state: CVState) -> str:
    if not state["violaciones"] or state["intentos"] >= MAX_INTENTOS:
        return "imprenta"
    return "pluma_redactar"
