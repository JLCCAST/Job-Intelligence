from pathlib import Path

import pandas as pd
import streamlit as st

from app import services
from ui.comun import encabezado, escribir, etiqueta_oferta, leer

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

encabezado("Postulaciones", "El estado de cada oferta y su historial.", seccion="Ofertas")

ofertas = leer("listar_ofertas")
estados = leer("listar_estados")
if not ofertas:
    st.info("Aún no tienes ofertas registradas. Analiza una en **Analizar oferta**.")
    st.stop()

# Embudo: cuántas ofertas hay en cada etapa.
conteo = {e: sum(1 for o in ofertas if o["estado"] == e) for e in estados}
ICONOS = {"Registrada": ":material/inbox:", "Analizada": ":material/visibility:", "Postulada": ":material/send:",
          "Entrevista": ":material/forum:", "Oferta": ":material/celebration:",
          "Rechazada": ":material/block:", "Descartada": ":material/delete:"}
with st.container(horizontal=True, gap="small"):
    for estado in estados:
        st.metric(estado, conteo[estado], border=True, icon=ICONOS.get(estado), width=135)
st.space("small")

filtro = st.multiselect("Filtrar por estado", estados, placeholder="Todos los estados")
visibles = [o for o in ofertas if not filtro or o["estado"] in filtro]

st.dataframe(
    pd.DataFrame(visibles)[["job_id", "puesto", "empresa", "estado", "match_score", "fuente", "fecha_registro", "url"]],
    hide_index=True,
    column_config={
        "job_id": "ID",
        "puesto": "Puesto",
        "empresa": "Empresa",
        "estado": "Estado",
        "match_score": st.column_config.ProgressColumn("Match Score", format="%.1f%%", min_value=0, max_value=100),
        "fuente": "Fuente",
        "fecha_registro": st.column_config.DatetimeColumn("Registrada", format="DD/MM/YYYY"),
        "url": st.column_config.LinkColumn("Enlace", display_text="Abrir"),
    },
)

st.subheader("Actualizar una postulación")
por_id = {o["job_id"]: o for o in ofertas}
job_id = st.selectbox("Oferta", list(por_id), format_func=lambda i: etiqueta_oferta(por_id[i]))
actual = por_id[job_id]["estado"]

with st.form("estado"):
    c1, c2 = st.columns([1, 2])
    nuevo = c1.selectbox("Nuevo estado", estados, index=estados.index(actual))
    nota = c2.text_input("Nota (opcional)", placeholder="Ej.: entrevista el jueves con RR. HH.")
    guardar = st.form_submit_button("Guardar", type="primary")

if guardar:
    if nuevo == actual and not nota.strip():
        st.info("No hay cambios que guardar.")
    else:
        escribir(services.cambiar_estado, job_id, nuevo, nota.strip())
        st.toast(f"Estado actualizado a {nuevo}.")
        st.rerun()

historial = leer("historial_estados", job_id)
if historial:
    st.caption("Historial")
    st.dataframe(
        pd.DataFrame(historial),
        hide_index=True,
        column_config={
            "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
            "estado": "Estado",
            "nota": "Nota",
        },
    )

st.subheader("CVs generados para esta oferta")
versiones = services.versiones_cv(job_id)
if not versiones:
    st.caption("Todavía no adaptaste tu CV a esta oferta.")
for v in versiones:
    cv = Path(v["ruta_cv"])
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        fecha = v["fecha"].replace("T", " ")[:16]
        st.markdown(f"**Versión {v['version']}** · {fecha}")
        if v["enviado"]:
            st.badge(f"Enviado el {v['fecha_envio'][:10]}", color="green", icon=":material/send:")
        if not v["usa_texto_de_pluma"]:
            st.badge("Textos originales", color="gray", help="El texto de Pluma no pasó el validador")
        if cv.exists():
            st.download_button("Descargar CV", cv.read_bytes(), file_name=cv.name, mime=DOCX,
                               key=f"cv_v{v['version']}", icon=":material/download:")
        else:
            st.caption("El archivo ya no está en tu PC")
if versiones and not any(v["enviado"] for v in versiones):
    st.caption("Al marcar la oferta como «Postulada», la última versión queda registrada como la enviada.")

if st.button("Adaptar mi CV a esta oferta", icon=":material/description:"):
    st.session_state["job_para_cv"] = job_id
    st.session_state.pop("flujo_cv", None)
    st.switch_page("ui/adaptar_cv.py")
