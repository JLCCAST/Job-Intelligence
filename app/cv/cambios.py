"""
cambios.py

Qué cambió la IA en tu CV, sin LLM: compara tu CV base con lo que
redactó Pluma y arma una lista de cambios que puedes aceptar o
rechazar antes de que Imprenta genere el Word.

La relación entre texto original y texto nuevo es por POSICIÓN: Pluma
recibe los bullets de cada ítem en un orden (seleccion) y debe
devolver la misma cantidad en el mismo orden (el Validador lo exige).
Así, el bullet k de Pluma corresponde al bullet seleccion[k] de tu CV.

Cada cambio trae un motivo calculado (qué términos de la oferta o qué
respuestas del Preguntón aparecen y antes no estaban). Notario lo
reemplaza por una explicación escrita con IA; este motivo queda como
respaldo si Gemini no está disponible.
"""

import difflib
import re
from typing import Optional

from app.cv.modelo import CVBase

NO_ES_TECNOLOGIA = {"inglés", "ingles", "english"}


def _aparece(termino: str, texto: str) -> bool:
    patron = r"(?<![\w])" + re.escape(termino) + r"(?![\w])"
    return re.search(patron, texto, flags=re.IGNORECASE) is not None


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def diferencias(original: str, nuevo: str) -> list[dict]:
    """
    Diferencias palabra por palabra, listas para pintar:
    [{"tipo": "igual" | "quitado" | "agregado", "texto": "..."}].
    """
    a = re.findall(r"\S+\s*", original)
    b = re.findall(r"\S+\s*", nuevo)
    # Se compara sin los espacios del final, para que "datos" y "datos "
    # cuenten como la misma palabra.
    matcher = difflib.SequenceMatcher(a=[x.strip() for x in a], b=[x.strip() for x in b], autojunk=False)
    partes: list[dict] = []

    def agregar(tipo: str, texto: str) -> None:
        if not texto:
            return
        if partes and partes[-1]["tipo"] == tipo:
            partes[-1]["texto"] += texto
        else:
            partes.append({"tipo": tipo, "texto": texto})

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            agregar("igual", "".join(b[j1:j2]))
        else:
            agregar("quitado", "".join(a[i1:i2]))
            agregar("agregado", "".join(b[j1:j2]))
    return partes


def similitud(original: str, nuevo: str) -> float:
    a, b = original.split(), nuevo.split()
    return round(difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio(), 2)


def motivo_calculado(original: str, nuevo: str, oferta: dict, confirmadas: list[str]) -> str:
    """El motivo que se puede comprobar comparando textos."""
    terminos = [
        r["nombre"] for r in oferta.get("requisitos", [])
        if r["nombre"].strip().lower() not in NO_ES_TECNOLOGIA
    ]
    nuevos_oferta = [t for t in terminos if _aparece(t, nuevo) and not _aparece(t, original)]
    nuevos_pregunton = [
        t for t in confirmadas
        if _aparece(t, nuevo) and not _aparece(t, original) and t not in nuevos_oferta
    ]
    partes = []
    if nuevos_oferta:
        partes.append(f"Usa términos de la oferta: {', '.join(nuevos_oferta)}.")
    if nuevos_pregunton:
        partes.append(f"Agrega lo que confirmaste en Preguntón: {', '.join(nuevos_pregunton)}.")
    return " ".join(partes) or "Reformulado con otras palabras."


def _titulo_item(item) -> str:
    return getattr(item, "nombre", None) or f"{item.empresa} — {item.cargo}"


def calcular_cambios(
    cv: CVBase,
    oferta: dict,
    seleccion: dict,
    redaccion: Optional[dict],
    respuestas_confirmadas: list[dict],
) -> list[dict]:
    """
    Un cambio por cada texto que Pluma reescribió (perfil y bullets).
    Los que quedaron idénticos no se listan: no hay nada que revisar.
    """
    if not redaccion:
        return []
    confirmadas = [r["tecnologia"] for r in respuestas_confirmadas]
    cambios: list[dict] = []

    def agregar(id_: str, seccion: str, item: str, original: str, nuevo: str) -> None:
        if _normalizar(original) == _normalizar(nuevo):
            return
        cambios.append({
            "id": id_,
            "seccion": seccion,
            "item": item,
            "original": original,
            "nuevo": nuevo,
            "diferencias": diferencias(original, nuevo),
            # 0 a 1: cuánto se parece al original. Si se reescribió casi
            # todo, la app muestra "antes / ahora" en vez de mezclar palabras.
            "similitud": similitud(original, nuevo),
            "motivo": motivo_calculado(original, nuevo, oferta, confirmadas),
            "motivo_de": "calculado",   # "notario" cuando lo explica la IA
            "requisitos": [],            # requisitos de la oferta que atiende (Notario)
            "atencion": None,            # aviso de Notario ("revisa que...")
            "alerta": None,              # lo que el código encontró mal en el motivo
        })

    agregar("perfil", "perfil", "Perfil profesional", cv.perfil, redaccion["perfil"])

    for seccion, items_cv in (("experiencia", cv.experiencia), ("proyectos", cv.proyectos)):
        redactados = {i["indice"]: i["logros"] for i in redaccion.get(seccion, [])}
        for sel in seleccion.get(seccion, []):
            nuevos = redactados.get(sel["indice"])
            if nuevos is None or len(nuevos) != len(sel["logros"]):
                continue  # el Validador ya lo habría rechazado
            item = items_cv[sel["indice"]]
            for posicion, (i_original, nuevo) in enumerate(zip(sel["logros"], nuevos)):
                agregar(
                    f"{seccion}-{sel['indice']}-{posicion}", seccion, _titulo_item(item),
                    item.logros[i_original], nuevo,
                )
    return cambios


def cambios_de_estructura(cv: CVBase, seleccion: dict) -> list[str]:
    """
    Lo que Pluma decidió sin reescribir texto: qué proyectos entraron,
    en qué orden y qué bullets quedaron fuera. Es informativo.
    """
    notas = []
    elegidos = [s["indice"] for s in seleccion.get("proyectos", [])]
    fuera = [cv.proyectos[i].nombre for i in range(len(cv.proyectos)) if i not in elegidos]
    if fuera:
        notas.append(f"Proyectos que no entraron por relevancia: {', '.join(fuera)}.")
    if elegidos != sorted(elegidos):
        orden = ", ".join(cv.proyectos[i].nombre for i in elegidos)
        notas.append(f"Proyectos ordenados por relevancia para la oferta: {orden}.")

    for seccion, items_cv in (("experiencia", cv.experiencia), ("proyectos", cv.proyectos)):
        for sel in seleccion.get(seccion, []):
            item = items_cv[sel["indice"]]
            omitidos = len(item.logros) - len(sel["logros"])
            if omitidos > 0:
                notas.append(
                    f"En «{_titulo_item(item)}» quedaron fuera {omitidos} "
                    f"{'bullet' if omitidos == 1 else 'bullets'} (máximo {len(sel['logros'])})."
                )
            elif sel["logros"] != sorted(sel["logros"]):
                notas.append(f"En «{_titulo_item(item)}» los bullets se reordenaron por relevancia.")
    return notas


def textos_con_decisiones(
    cv: CVBase, seleccion: dict, redaccion: dict, rechazados: set[str]
) -> tuple[str, dict, dict]:
    """
    Perfil y bullets finales: el texto de Pluma, salvo en los cambios
    que rechazaste, donde vuelve tu texto original.
    """
    perfil = cv.perfil if "perfil" in rechazados else redaccion["perfil"]
    finales = {}
    for seccion, items_cv in (("experiencia", cv.experiencia), ("proyectos", cv.proyectos)):
        redactados = {i["indice"]: i["logros"] for i in redaccion.get(seccion, [])}
        por_item = {}
        for sel in seleccion.get(seccion, []):
            item = items_cv[sel["indice"]]
            nuevos = redactados.get(sel["indice"], [])
            textos = []
            for posicion, i_original in enumerate(sel["logros"]):
                id_ = f"{seccion}-{sel['indice']}-{posicion}"
                if id_ in rechazados or posicion >= len(nuevos):
                    textos.append(item.logros[i_original])
                else:
                    textos.append(nuevos[posicion])
            por_item[sel["indice"]] = textos
        finales[seccion] = por_item
    return perfil, finales["experiencia"], finales["proyectos"]
