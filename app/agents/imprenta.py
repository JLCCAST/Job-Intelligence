"""
imprenta.py -- agente Imprenta

Tarea fija: generar los dos DOCX de una postulación, sin LLM:

    CV_<empresa>_<puesto>.docx       -> listo para enviar
    Brechas_<empresa>_<puesto>.docx  -> qué te falta y qué estudiar

Regla de seguridad: el texto de Pluma solo se usa si pasó el
validador. Si después de los reintentos seguía con problemas, el CV
sale con tus bullets ORIGINALES (ya ordenados por relevancia) y el
documento de brechas explica por qué.
"""

import re
from datetime import datetime
import unicodedata
from pathlib import Path
from typing import Optional

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt, RGBColor

from app.agents.estado import CVState
from app.cv import historial
from app.cv.cargador import RAIZ, cargar_cv_base
from app.cv.modelo import CVBase

CARPETA_SALIDAS = RAIZ / "salidas"

# A4 con márgenes de 0.5", igual que tu CV v2.
ANCHO_A4, ALTO_A4 = Emu(7560310), Emu(10692130)
MARGEN = Emu(457200)
FUENTE = "Calibri"
COLOR_TITULOS = RGBColor(0x1F, 0x3A, 0x5F)


# --------------------------------------------------------------
# Utilidades de formato
# --------------------------------------------------------------

def _slug(texto: Optional[str], largo: int = 40) -> str:
    if not texto:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", sin_tildes).strip("_")[:largo]


def _nombre_archivo(prefijo: str, oferta: dict) -> str:
    partes = [prefijo, _slug(oferta.get("empresa")), _slug(oferta["puesto"])]
    return "_".join(p for p in partes if p) + ".docx"


def _documento_base() -> Document:
    doc = Document()
    seccion = doc.sections[0]
    seccion.page_width, seccion.page_height = ANCHO_A4, ALTO_A4
    for lado in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(seccion, lado, MARGEN)

    normal = doc.styles["Normal"]
    normal.font.name = FUENTE
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(2)
    return doc


def _ancho_util() -> Emu:
    return Emu(ANCHO_A4 - 2 * MARGEN)


def _linea_inferior(parrafo) -> None:
    """Borde inferior fino bajo los títulos de sección."""
    pPr = parrafo._p.get_or_add_pPr()
    bordes = OxmlElement("w:pBdr")
    abajo = OxmlElement("w:bottom")
    for atributo, valor in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "1F3A5F")):
        abajo.set(qn(atributo), valor)
    bordes.append(abajo)
    pPr.append(bordes)


def _titulo_seccion(doc, texto: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(texto.upper())
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = COLOR_TITULOS
    _linea_inferior(p)


def _vineta(doc, texto: str):
    p = doc.add_paragraph(texto, style="List Bullet")
    p.paragraph_format.space_after = Pt(1)
    return p


def _encabezado_item(doc, izquierda: str, derecha: Optional[str] = None) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.tab_stops.add_tab_stop(_ancho_util(), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run(izquierda).bold = True
    if derecha:
        p.add_run("\t" + derecha)


def _etiqueta_valor(doc, etiqueta: str, valor: str) -> None:
    p = doc.add_paragraph()
    p.add_run(etiqueta).bold = True
    p.add_run(valor)


# --------------------------------------------------------------
# CV
# --------------------------------------------------------------

def _textos_finales(cv: CVBase, state: CVState) -> tuple[str, dict, dict, list[str]]:
    """Decide si se usa lo de Pluma o tus textos originales."""
    seleccion = state["seleccion"]
    redaccion = state.get("redaccion")
    usar_pluma = redaccion is not None and not state.get("violaciones")

    def originales(items_cv, seleccion_items):
        return {s["indice"]: [items_cv[s["indice"]].logros[i] for i in s["logros"]] for s in seleccion_items}

    if not usar_pluma:
        return (
            cv.perfil,
            originales(cv.experiencia, seleccion["experiencia"]),
            originales(cv.proyectos, seleccion["proyectos"]),
            [],
        )
    return (
        redaccion["perfil"],
        {i["indice"]: i["logros"] for i in redaccion["experiencia"]},
        {i["indice"]: i["logros"] for i in redaccion["proyectos"]},
        redaccion["habilidades_destacadas"],
    )


def generar_cv(cv: CVBase, state: CVState, carpeta: Path) -> Path:
    perfil, logros_exp, logros_proy, destacadas = _textos_finales(cv, state)
    destacadas_min = [d.strip().lower() for d in destacadas]
    doc = _documento_base()

    # --- Encabezado ---
    c = cv.contacto
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(c.nombre.upper())
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = COLOR_TITULOS
    for linea in (
        [c.email, c.telefono, c.ubicacion],
        [c.linkedin, c.github],
    ):
        texto = " · ".join(x for x in linea if x)
        if texto:
            doc.add_paragraph(texto).alignment = WD_ALIGN_PARAGRAPH.CENTER

    _titulo_seccion(doc, "Perfil profesional")
    doc.add_paragraph(perfil).alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    if logros_exp:
        _titulo_seccion(doc, "Experiencia laboral")
        for sel in state["seleccion"]["experiencia"]:
            e = cv.experiencia[sel["indice"]]
            izquierda = f"{e.empresa} — {e.cargo}" + (f" | {e.ubicacion}" if e.ubicacion else "")
            _encabezado_item(doc, izquierda, f"{e.inicio} – {e.fin}")
            for logro in logros_exp[sel["indice"]]:
                _vineta(doc, logro)

    if logros_proy:
        _titulo_seccion(doc, "Proyectos")
        for sel in state["seleccion"]["proyectos"]:
            pr = cv.proyectos[sel["indice"]]
            izquierda = pr.nombre + (f" | {pr.contexto}" if pr.contexto else "")
            _encabezado_item(doc, izquierda, pr.fecha)
            for logro in logros_proy[sel["indice"]]:
                # Mantiene el proyecto junto con su línea de Stack.
                _vineta(doc, logro).paragraph_format.keep_with_next = bool(pr.stack)
            if pr.stack:
                _etiqueta_valor(doc, "Stack: ", " · ".join(pr.stack))

    if cv.habilidades:
        _titulo_seccion(doc, "Habilidades técnicas")
        for grupo in cv.habilidades:
            # Las habilidades destacadas por Pluma van primero en su grupo.
            items = sorted(grupo.items, key=lambda h: h.nombre.strip().lower() not in destacadas_min)
            texto = " · ".join(f"{h.nombre} ({h.nivel})" if h.nivel else h.nombre for h in items)
            _etiqueta_valor(doc, f"{grupo.grupo}: ", texto)

    if cv.educacion:
        _titulo_seccion(doc, "Educación")
        for ed in cv.educacion:
            fechas = " – ".join(x for x in (ed.inicio, ed.fin) if x)
            _encabezado_item(doc, ed.titulo, fechas or None)
            doc.add_paragraph(ed.institucion)

    if cv.logros:
        _titulo_seccion(doc, "Logros destacados")
        for lo in cv.logros:
            _encabezado_item(doc, lo.titulo)
            if lo.descripcion:
                doc.add_paragraph(lo.descripcion)

    if cv.certificados:
        _titulo_seccion(doc, "Certificados")
        for ce in cv.certificados:
            _vineta(doc, f"{ce.nombre} — {ce.emisor}")

    if cv.idiomas:
        _titulo_seccion(doc, "Idiomas")
        doc.add_paragraph(" · ".join(f"{i.idioma}: {i.nivel}" for i in cv.idiomas))

    if cv.competencias:
        _titulo_seccion(doc, "Competencias")
        doc.add_paragraph(" · ".join(cv.competencias))

    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / _nombre_archivo("CV", state["oferta"])
    doc.save(ruta)
    return ruta


# --------------------------------------------------------------
# Brechas
# --------------------------------------------------------------

NIVEL_LEGIBLE = {"basico": "Básico", "intermedio": "Intermedio", "avanzado": "Avanzado"}


def _nivel(nivel: Optional[str]) -> str:
    return NIVEL_LEGIBLE.get(nivel or "", "—")


ESTADO_CUMPLE = "Cumples"
ESTADO_NIVEL_MENOR = "Nivel menor al pedido"
ESTADO_CONFIRMADO = "Confirmado en Preguntón"
ESTADO_SOLO_CV = "En tu CV (no en tu perfil)"
ESTADO_FALTA = "Te falta"


def clasificar_requisitos(oferta: dict, skills_cv: set[str], confirmadas: set[str]) -> list[dict]:
    filas = []
    for r in oferta["requisitos"]:
        clave = r["nombre"].strip().lower()
        if r["nivel_usuario"] is not None:
            estado = ESTADO_NIVEL_MENOR if r.get("bajo_nivel") else ESTADO_CUMPLE
        elif clave in confirmadas:
            estado = ESTADO_CONFIRMADO
        elif clave in skills_cv:
            estado = ESTADO_SOLO_CV
        else:
            estado = ESTADO_FALTA
        filas.append({**r, "estado": estado})
    return filas


def prioridades_de_estudio(filas: list[dict]) -> list[dict]:
    """Primero lo obligatorio que falta, luego lo obligatorio flojo, luego lo deseable."""
    def prioridad(f):
        if f["estado"] == ESTADO_FALTA and f["requirement_type"] == "required":
            return 0
        if f["estado"] == ESTADO_NIVEL_MENOR:
            return 1
        if f["estado"] == ESTADO_FALTA:
            return 2
        return None

    candidatas = [f for f in filas if prioridad(f) is not None]
    return sorted(candidatas, key=prioridad)


def generar_brechas(cv: CVBase, state: CVState, carpeta: Path) -> Path:
    oferta = state["oferta"]
    confirmadas = {r["tecnologia"].strip().lower() for r in state.get("respuestas_confirmadas", [])}
    filas = clasificar_requisitos(oferta, cv.skills_declaradas(), confirmadas)
    doc = _documento_base()

    p = doc.add_paragraph()
    run = p.add_run(f"Brechas — {oferta['puesto']}")
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = COLOR_TITULOS
    doc.add_paragraph(f"Empresa: {oferta.get('empresa') or 'no especificada'} · job_id {oferta['job_id']}")

    score = oferta.get("match_score")
    _etiqueta_valor(doc, "Match Score: ", f"{score:.1f}%" if score is not None else "sin datos para calcular")
    if oferta.get("cumple_ingles") is False:
        _etiqueta_valor(doc, "Inglés: ", "por debajo del nivel pedido")

    _titulo_seccion(doc, "Requisitos de la oferta")
    tabla = doc.add_table(rows=1, cols=5)
    tabla.style = "Light Grid Accent 1"
    tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
    for celda, texto in zip(tabla.rows[0].cells, ("Requisito", "Tipo", "Nivel pedido", "Tu nivel", "Estado")):
        celda.text = texto
    for f in filas:
        celdas = tabla.add_row().cells
        celdas[0].text = f["nombre"]
        celdas[1].text = "Obligatorio" if f["requirement_type"] == "required" else "Deseable"
        celdas[2].text = _nivel(f.get("nivel_pedido"))
        celdas[3].text = _nivel(f.get("nivel_usuario"))
        celdas[4].text = f["estado"]

    _titulo_seccion(doc, "Qué estudiar primero")
    prioridades = prioridades_de_estudio(filas)
    if not prioridades:
        doc.add_paragraph("Cubres todos los requisitos de la oferta.")
    for f in prioridades:
        tipo = "obligatorio" if f["requirement_type"] == "required" else "deseable"
        if f["estado"] == ESTADO_NIVEL_MENOR:
            _vineta(doc, f"{f['nombre']} ({tipo}): ya lo usas, pero piden nivel {_nivel(f['nivel_pedido']).lower()}. "
                         "Refuérzalo con un proyecto que lo demuestre.")
        else:
            _vineta(doc, f"{f['nombre']} ({tipo}): no aparece en tu perfil.")

    _titulo_seccion(doc, "Cómo abordarlo en la entrevista")
    faltan_obligatorios = [f["nombre"] for f in filas if f["estado"] == ESTADO_FALTA and f["requirement_type"] == "required"]
    flojos = [f["nombre"] for f in filas if f["estado"] == ESTADO_NIVEL_MENOR]
    if faltan_obligatorios:
        _vineta(doc, f"Si preguntan por {', '.join(faltan_obligatorios)}: reconoce que aún no lo usaste en un "
                     "proyecto y explica cómo lo aprenderías apoyándote en lo que sí dominas.")
    if flojos:
        _vineta(doc, f"Para {', '.join(flojos)}: prepara un ejemplo concreto de tu CV donde lo usaste y "
                     "qué te faltaría para el nivel pedido.")
    if not faltan_obligatorios and not flojos:
        doc.add_paragraph("No hay brechas obligatorias: prepara ejemplos concretos de tus proyectos para cada requisito.")

    solo_cv = [f["nombre"] for f in filas if f["estado"] == ESTADO_SOLO_CV]
    avisos = []
    if solo_cv:
        avisos.append(
            f"{', '.join(solo_cv)} aparece en tu CV pero no en tu perfil (user_skill), así que no suma a tu "
            "Match Score. Agrégalo con scripts/cargar_mi_perfil.py."
        )
    if state.get("violaciones"):
        avisos.append(
            "El texto adaptado por Pluma no pasó el validador, así que el CV usa tus bullets originales "
            "(ordenados por relevancia). Motivos: " + " ".join(state["violaciones"])
        )
    if avisos:
        _titulo_seccion(doc, "Avisos")
        for aviso in avisos:
            _vineta(doc, aviso)

    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / _nombre_archivo("Brechas", oferta)
    doc.save(ruta)
    return ruta


def imprimir(state: CVState) -> CVState:
    """
    Cada adaptación queda en su propia carpeta y en el historial, sin
    pisar las anteriores: salidas/cv/job_<id>/v<n>_<fecha>/CV_....docx
    (el nombre del archivo se mantiene limpio para enviarlo tal cual).
    """
    oferta = state["oferta"]
    version = 1 + len(historial.versiones(oferta["job_id"]))
    carpeta = (
        CARPETA_SALIDAS / "cv" / f"job_{oferta['job_id']}"
        / f"v{version}_{datetime.now():%Y-%m-%d_%H%M}"
    )
    cv = cargar_cv_base()
    ruta_cv = str(generar_cv(cv, state, carpeta))
    ruta_brechas = str(generar_brechas(cv, state, carpeta))
    historial.registrar(
        oferta["job_id"], oferta["puesto"], oferta.get("empresa"), ruta_cv, ruta_brechas,
        usa_texto_de_pluma=bool(state.get("redaccion")) and not state.get("violaciones"),
    )
    return {"ruta_cv": ruta_cv, "ruta_brechas": ruta_brechas}
