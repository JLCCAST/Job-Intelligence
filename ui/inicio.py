from datetime import date

import streamlit as st

from app import services
from ui.comun import ANCHO_INDICADOR, ESTADOS_ACTIVOS, acceso, formato_score, hero, leer, plural, tarjeta_oferta

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

ofertas = leer("listar_ofertas")
por_revisar = leer("tecnologias_para_revisar")
resumen = leer("resumen_centinela")

try:
    nombre = services.cargar_cv_base().contacto.nombre.split()[0].capitalize()
except services.CVBaseNoEncontrado:
    nombre = None

bandeja = sorted((o for o in ofertas if o["estado"] == "Registrada"),
                 key=lambda o: o["match_score"] or 0, reverse=True)
activas = [o for o in ofertas if o["estado"] in ESTADOS_ACTIVOS]
scores = [o["match_score"] for o in ofertas if o["match_score"] is not None]
nuevas = len(resumen["nuevas"])

hoy = date.today()
hero(
    f"Hola, {nombre}" if nombre else "Hola",
    f"Tienes {plural(len(bandeja), 'oferta', 'ofertas')} en tu bandeja"
    + (f" ({plural(nuevas, 'nueva', 'nuevas')} en las últimas 24 horas)" if nuevas else "")
    + (f" y {plural(len(activas), 'postulación', 'postulaciones')} en curso." if activas
       else " y ninguna postulación en curso."),
    f"{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]}",
)

# Contenedor horizontal: si la ventana es angosta, pasan a 2 filas en vez de cortar el texto.
with st.container(horizontal=True, gap="small"):
    st.metric("Ofertas registradas", len(ofertas), border=True, icon=":material/database:", width=ANCHO_INDICADOR)
    st.metric("En tu bandeja", len(bandeja), border=True, icon=":material/inbox:", width=ANCHO_INDICADOR)
    st.metric("Postulaciones activas", len(activas), border=True, icon=":material/send:",
              help="Postulada, Entrevista u Oferta", width=ANCHO_INDICADOR)
    st.metric("Match Score promedio", formato_score(sum(scores) / len(scores)) if scores else "—",
              border=True, icon=":material/target:", width=ANCHO_INDICADOR)

st.space("small")

# Avisos a todo el ancho (no en columna lateral): en pantallas angostas
# una columna estrecha cortaba las palabras.
for r in resumen["recordatorios"]:
    st.warning(f"**{r['puesto']}** · {r['empresa']}: {r['dias']} días sin respuesta. Buen momento para hacer seguimiento.",
               icon=":material/schedule:")
if por_revisar:
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        st.markdown(f":material/rule: **{plural(len(por_revisar), 'tecnología nueva espera', 'tecnologías nuevas esperan')}** tu revisión.")
        st.page_link("ui/revision.py", label="Revisar catálogo", icon=":material/arrow_forward:")

st.subheader("Mejores ofertas por revisar")
if not bandeja:
    st.info("Tu bandeja está vacía. Analiza una oferta o deja que Sabueso traiga nuevas.",
            icon=":material/inbox:")
for o in bandeja[:3]:
    acciones = tarjeta_oferta(o, mostrar_estado=False)
    if acciones.button("Adaptar mi CV", key=f"cv_{o['job_id']}", icon=":material/edit_document:"):
        st.session_state["job_para_cv"] = o["job_id"]
        st.session_state.pop("flujo_cv", None)
        st.switch_page("ui/adaptar_cv.py")
if len(bandeja) > 3:
    st.page_link("ui/bandeja.py", label=f"Ver las {len(bandeja)} ofertas de tu bandeja",
                 icon=":material/arrow_forward:")

st.space("small")
st.subheader("Accesos rápidos")
with st.container(horizontal=True, gap="small"):
    acceso("ui/analizar.py", "Analizar oferta", "Pega una oferta y mide tu encaje.", ":material/document_search:")
    acceso("ui/bandeja.py", "Bandeja", "Ofertas que trajo Sabueso.", ":material/inbox:")
    acceso("ui/adaptar_cv.py", "Adaptar CV", "CV y brechas en Word.", ":material/edit_document:")
    acceso("ui/que_estudiar.py", "Qué estudiar", "Prioridades y plan de Brújula.", ":material/explore:")
