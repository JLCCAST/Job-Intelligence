"""
eventos.py

Lo que hace visible el trabajo de los agentes:

- AGENTES: el equipo, con su tarea y qué nodos del grafo le pertenecen.
- transmitir(): corre un grafo de Batuta con stream_mode="tasks" y
  convierte cada inicio/fin de nodo en un evento legible ("Lupa:
  encontré 8 requisitos", "Validador: rechacé el texto..."). Son los
  eventos REALES de LangGraph, no una animación.
- registrar()/actividad_reciente(): un registro local de lo que hizo
  cada agente (data/actividad.jsonl, privado) para la página Agentes.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from app.cv.cargador import RAIZ

RUTA_ACTIVIDAD = RAIZ / "data" / "actividad.jsonl"
MAX_REGISTROS = 400

# Orden = orden en que aparecen en la app. "gemini": agente que llama al
# LLM; "modelo": clave en app.gemini.MODELOS_POR_AGENTE.
AGENTES = [
    {"id": "batuta", "nombre": "Batuta", "rol": "Orquestador",
     "tarea": "Coordina a los demás agentes con LangGraph: decide el orden, las pausas y los reintentos, y guarda el progreso.",
     "gemini": False, "flujo": "ambos"},
    {"id": "sabueso", "nombre": "Sabueso", "rol": "Buscador",
     "tarea": "Busca ofertas nuevas cada día en fuentes permitidas, filtra por país, título y seniority, y descarta duplicados.",
     "gemini": False, "flujo": "rutina"},
    {"id": "lupa", "nombre": "Lupa", "rol": "Extractor",
     "tarea": "Lee la oferta y extrae requisitos, empresa, área e inglés con la frase que respalda cada uno.",
     "gemini": True, "modelo": "lupa", "flujo": "oferta"},
    {"id": "archivero", "nombre": "Archivero", "rol": "Normalizador",
     "tarea": "Une tecnologías y empresas con el catálogo (alias o nombre canónico) y guarda la oferta.",
     "gemini": False, "flujo": "oferta"},
    {"id": "balanza", "nombre": "Balanza", "rol": "Evaluador",
     "tarea": "Calcula el Match Score con una fórmula fija y separa lo que cumples de lo que te falta.",
     "gemini": False, "flujo": "ambos"},
    {"id": "pregunton", "nombre": "Preguntón", "rol": "Entrevistador",
     "tarea": "Antes de escribir, te pregunta por lo que la oferta pide y no está en tu CV. Recuerda tus respuestas.",
     "gemini": False, "flujo": "cv"},
    {"id": "pluma", "nombre": "Pluma", "rol": "Redactor",
     "tarea": "Elige tus proyectos más relevantes y reescribe el CV con el vocabulario de la oferta.",
     "gemini": True, "modelo": "pluma", "flujo": "cv"},
    {"id": "validador", "nombre": "Validador", "rol": "Control de calidad",
     "tarea": "Revisa el texto de Pluma: rechaza tecnologías o cifras que no estén en tu CV ni hayas confirmado.",
     "gemini": False, "flujo": "cv"},
    {"id": "imprenta", "nombre": "Imprenta", "rol": "Documentador",
     "tarea": "Genera el CV listo para enviar y el informe de brechas en Word.",
     "gemini": False, "flujo": "cv"},
    {"id": "centinela", "nombre": "Centinela", "rol": "Seguimiento",
     "tarea": "Arma el resumen diario, te recuerda las postulaciones sin respuesta y te avisa en Windows.",
     "gemini": False, "flujo": "rutina"},
    {"id": "brujula", "nombre": "Brújula", "rol": "Mentor",
     "tarea": "Calcula qué te conviene estudiar según tus ofertas y arma un plan con un proyecto por tecnología.",
     "gemini": True, "modelo": "brujula", "flujo": "rutina"},
]

# Nodo del grafo -> (agente, qué está haciendo mientras trabaja)
NODOS = {
    "lupa_leer": ("lupa", "Leyendo la oferta"),
    "lupa_extraer": ("lupa", "Extrayendo requisitos con Gemini"),
    "archivero": ("archivero", "Normalizando y guardando la oferta"),
    "balanza": ("balanza", "Calculando tu Match Score"),
    "balanza_preparar": ("balanza", "Revisando qué pide la oferta y qué cumples"),
    "pregunton": ("pregunton", "Buscando lo que falta en tu CV"),
    "pluma_seleccionar": ("pluma", "Eligiendo tus proyectos más relevantes"),
    "pluma_redactar": ("pluma", "Redactando el CV con Gemini"),
    "pluma_validar": ("validador", "Revisando que no haya nada inventado"),
    "imprenta": ("imprenta", "Generando los documentos en Word"),
}


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def resumir(nodo: str, r: dict, interrupciones: list) -> tuple[str, str]:
    """(estado, resumen) de lo que acaba de hacer un nodo. Estado: ok | detenido | pausa | rechazo | error."""
    if nodo == "lupa_leer":
        if r.get("registration_status") == "duplicate":
            return "detenido", f"Esa oferta ya estaba registrada (job_id {r.get('job_id')}). Me detengo aquí."
        if r.get("terminado"):
            return "error", f"No pude leer la página: {r.get('error_detail')}"
        aviso = " Es corto: puede faltar parte de la oferta." if r.get("extraction_status") == "partial" else ""
        return "ok", f"Leí la oferta ({r.get('raw_length', 0):,} caracteres).{aviso}".replace(",", ".")

    if nodo == "lupa_extraer":
        if r.get("registration_status") == "offer_closed":
            return "detenido", "La oferta ya no está disponible: no la registro."
        if r.get("terminado"):
            return "error", f"Gemini no respondió: {(r.get('error_detail') or '')[:140]}"
        e = r["extraction"]
        tecnologias = e.technologies if hasattr(e, "technologies") else e.get("technologies", [])
        titulo = e.job_title if hasattr(e, "job_title") else e.get("job_title")
        obligatorias = sum(1 for t in tecnologias if (t.requirement_type if hasattr(t, "requirement_type") else t["requirement_type"]) == "required")
        return "ok", f"«{titulo}»: {_plural(len(tecnologias), 'requisito', 'requisitos')} ({obligatorias} obligatorios)."

    if nodo == "archivero":
        extra = ""
        if r.get("tecnologias_creadas"):
            extra = f" Agregué al catálogo: {', '.join(r['tecnologias_creadas'])}."
        return "ok", f"Guardé la oferta (job_id {r.get('job_id')}).{extra}"

    if nodo == "balanza":
        score = r.get("match_score")
        faltan = r.get("tecnologias_faltantes") or []
        texto = f"Match Score: {score:.1f}%." if score is not None else "La oferta no pide nada evaluable."
        if faltan:
            texto += f" Te falta: {', '.join(faltan[:4])}{'…' if len(faltan) > 4 else ''}."
        return "ok", texto

    if nodo == "balanza_preparar":
        reqs = r.get("oferta", {}).get("requisitos", [])
        cumples = sum(1 for q in reqs if q.get("nivel_usuario"))
        return "ok", f"La oferta pide {_plural(len(reqs), 'requisito', 'requisitos')}; cumples {cumples}."

    if nodo == "pregunton":
        if interrupciones:
            n = len(interrupciones[0].get("value", {}).get("preguntas", []))
            return "pausa", f"Tengo {_plural(n, 'pregunta', 'preguntas')} para ti. Espero tus respuestas."
        confirmadas = len(r.get("respuestas_confirmadas") or [])
        if r.get("preguntas"):
            return "ok", f"Guardé tus respuestas ({confirmadas} confirmadas)."
        return "ok", "No tengo nada que preguntarte: tu CV cubre lo que piden."

    if nodo == "pluma_seleccionar":
        sel = r.get("seleccion", {})
        return "ok", f"Elegí {_plural(len(sel.get('proyectos', [])), 'proyecto', 'proyectos')} y ordené los bullets por relevancia."

    if nodo == "pluma_redactar":
        if r.get("redaccion") is None:
            return "error", f"Gemini falló: {(r.get('error_detail') or '')[:140]}"
        red = r["redaccion"]
        bullets = sum(len(i["logros"]) for s in ("experiencia", "proyectos") for i in red[s])
        return "ok", f"Redacté el perfil y {_plural(bullets, 'bullet', 'bullets')}."

    if nodo == "pluma_validar":
        v = r.get("violaciones") or []
        if not v:
            return "ok", f"Aprobé el texto al intento {r.get('intentos')}: nada inventado."
        if r.get("intentos", 0) >= 3:
            return "rechazo", f"Sigue con {_plural(len(v), 'problema', 'problemas')}: Imprenta usará tus textos originales."
        return "rechazo", f"Rechacé el texto ({_plural(len(v), 'problema', 'problemas')}). Pluma lo corrige."

    if nodo == "imprenta":
        return "ok", "Generé tu CV y el informe de brechas en Word."

    return "ok", "Listo."


# --------------------------------------------------------------
# Transmisión en vivo
# --------------------------------------------------------------

def transmitir(grafo, entrada, config: Optional[dict] = None, flujo: str = "") -> Iterator[dict]:
    """
    Corre el grafo y va entregando eventos. Al final entrega
    {"tipo": "_estado", "estado": <estado acumulado>} para que quien
    llama arme la respuesta completa.
    """
    estado = dict(entrada) if isinstance(entrada, dict) else {}
    inicios: dict[str, float] = {}
    for ev in grafo.stream(entrada, config, stream_mode="tasks"):
        nodo = ev["name"]
        if nodo not in NODOS:
            continue
        agente, accion = NODOS[nodo]
        if "input" in ev:  # empieza
            inicios[ev["id"]] = time.perf_counter()
            yield {"tipo": "inicio", "nodo": nodo, "agente": agente, "accion": accion}
            continue
        ms = int((time.perf_counter() - inicios.pop(ev["id"], time.perf_counter())) * 1000)
        if ev.get("error"):
            yield {"tipo": "fin", "nodo": nodo, "agente": agente, "estado": "error", "resumen": str(ev["error"])[:200], "ms": ms}
            continue
        resultado = ev.get("result") or {}
        estado.update(resultado)
        est, resumen = resumir(nodo, resultado, ev.get("interrupts") or [])
        evento = {"tipo": "fin", "nodo": nodo, "agente": agente, "estado": est, "resumen": resumen, "ms": ms}
        registrar(agente, resumen, est, flujo)
        yield evento
    yield {"tipo": "_estado", "estado": estado}


# --------------------------------------------------------------
# Registro de actividad
# --------------------------------------------------------------

def registrar(agente: str, resumen: str, estado: str = "ok", flujo: str = "", ruta: Optional[Path] = None) -> None:
    ruta = ruta or RUTA_ACTIVIDAD
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        linea = json.dumps({
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "agente": agente, "estado": estado, "resumen": resumen, "flujo": flujo,
        }, ensure_ascii=False)
        lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
        lineas = (lineas + [linea])[-MAX_REGISTROS:]
        ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    except OSError:
        pass  # el registro es informativo: nunca debe romper un flujo


def actividad_reciente(limite: int = 60, ruta: Optional[Path] = None) -> list[dict]:
    ruta = ruta or RUTA_ACTIVIDAD
    if not ruta.exists():
        return []
    filas = [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
    return list(reversed(filas))[:limite]
