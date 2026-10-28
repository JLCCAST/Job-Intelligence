from pathlib import Path

import pandas as pd
import streamlit as st

from app import services
from ui.comun import plural, consultar, encabezado, escribir, leer

MUESTRA_MINIMA = 10
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

encabezado(
    "Qué estudiar",
    "Brújula ordena lo que te falta según cuántas de tus ofertas lo piden, qué tan lejos estás "
    "y si su demanda sube. Prioridad = demanda × distancia × tendencia.",
    seccion="Tú",
)

datos = leer("prioridades_estudio")
prioridades, total = datos["prioridades"], datos["total_ofertas"]

if total == 0:
    st.info("Aún no hay ofertas. Analiza algunas o deja que Sabueso las traiga.")
    st.stop()
if total < MUESTRA_MINIMA:
    st.warning(
        f"Calculado con {plural(total, 'oferta', 'ofertas')}. Con menos de {MUESTRA_MINIMA} el ranking refleja tus "
        "ofertas, no el mercado; la tendencia aparecerá cuando haya ofertas de al menos dos meses."
    )
if not prioridades:
    st.success("Cubres todo lo que piden tus ofertas.")
    st.stop()

# ---------- Ranking ----------
df = pd.DataFrame(prioridades)
st.dataframe(
    df[["tecnologia", "estado", "ofertas", "obligatoria_en", "tendencia_txt", "prioridad"]],
    hide_index=True,
    column_config={
        "tecnologia": "Tecnología",
        "estado": "Estado",
        "ofertas": st.column_config.NumberColumn("Ofertas", help="En cuántas ofertas aparece"),
        "obligatoria_en": st.column_config.NumberColumn("Obligatoria en"),
        "tendencia_txt": "Tendencia",
        "prioridad": st.column_config.ProgressColumn(
            "Prioridad", format="%.2f", min_value=0, max_value=float(df["prioridad"].max()),
        ),
    },
)

# ---------- Plan de estudio ----------
st.subheader("Plan de estudio")
plan = leer("cargar_plan_estudio")
etiqueta = "Actualizar plan con Gemini" if plan else "Generar plan con Gemini"
if st.button(etiqueta, type="primary", icon=":material/auto_awesome:"):
    with st.spinner("Armando tu plan para las 5 primeras..."):
        r = escribir(services.generar_plan_estudio)
    if r["error"]:
        st.error(r["error"])
    else:
        st.rerun()

if plan:
    st.caption(f"Generado el {plan['generado'].replace('T', ' a las ')}. Si registras ofertas nuevas, actualízalo.")
    st.write(plan["plan"]["resumen"])
    for item in plan["plan"]["items"]:
        with st.expander(f"{item['tecnologia']} · ~{item['semanas']} semanas"):
            st.write(item["por_que"])
            for tema in item["que_aprender"]:
                st.markdown(f"- {tema}")
            st.markdown(f"**Proyecto:** {item['proyecto']}")

# ---------- Ya lo aprendí ----------
st.subheader("Ya lo aprendí")
st.caption(
    "Marca solo lo que puedas demostrar (un proyecto, un curso con práctica). Se agrega a tu perfil "
    "y Balanza recalcula tus Match Score."
)
por_nombre = {p["tecnologia"]: p for p in prioridades}
with st.form("aprendido"):
    c1, c2 = st.columns(2)
    tech = c1.selectbox("Tecnología", list(por_nombre))
    nivel = c2.selectbox("Nivel", ["basico", "intermedio", "avanzado"], format_func=str.capitalize)
    evidencia = st.text_input("Evidencia", placeholder="Ej.: proyecto X en GitHub, curso Y con laboratorio")
    guardar = st.form_submit_button("Agregar a mi perfil")
if guardar:
    if not evidencia.strip():
        st.error("Escribe la evidencia: es lo que te respalda si te preguntan en una entrevista.")
    else:
        with st.spinner("Guardando y recalculando tus Match Score..."):
            escribir(services.guardar_habilidad, tech, por_nombre[tech]["categoria"], nivel, None, evidencia.strip())
        st.toast(f"{tech} agregado a tu perfil.")
        st.rerun()

# ---------- Informe ----------
st.divider()
if st.button("Generar informe en Word", icon=":material/description:"):
    ruta = Path(consultar(services.generar_informe_brujula))
    st.download_button("Descargar informe", ruta.read_bytes(), file_name=ruta.name, mime=DOCX,
                       icon=":material/download:")
