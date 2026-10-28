from pathlib import Path

import streamlit as st

from app import services
from ui.comun import consultar, encabezado, etiqueta_oferta, leer, pasos

encabezado(
    "Adaptar CV",
    "Preguntón te consulta lo que falta, Pluma adapta tu CV sin inventar nada "
    "e Imprenta genera el CV y el informe de brechas en Word.",
    seccion="Ofertas",
)
PASOS = ["Elegir oferta", "Responder preguntas", "Descargar documentos"]

try:
    services.cargar_cv_base()
except services.CVBaseNoEncontrado as exc:
    st.error(str(exc))
    st.stop()

ofertas = leer("listar_ofertas")
if not ofertas:
    st.info("Aún no tienes ofertas registradas. Analiza una en **Analizar oferta**.")
    st.stop()

flujo_previo = st.session_state.get("flujo_cv")
if flujo_previo is None:
    paso = 0
elif flujo_previo["esperando_respuestas"]:
    paso = 1
else:
    paso = 3
pasos(PASOS, paso)
st.space("small")

ids = [o["job_id"] for o in ofertas]
por_id = {o["job_id"]: o for o in ofertas}
preseleccion = st.session_state.get("job_para_cv")
job_id = st.selectbox(
    "Oferta",
    ids,
    index=ids.index(preseleccion) if preseleccion in ids else 0,
    format_func=lambda i: etiqueta_oferta(por_id[i]),
)

if st.button("Adaptar CV", type="primary", icon=":material/auto_awesome:"):
    with st.spinner("Preparando la adaptación..."):
        st.session_state["flujo_cv"] = consultar(services.iniciar_adaptacion_cv, job_id)
        st.session_state["flujo_cv_job"] = job_id

flujo = st.session_state.get("flujo_cv")
if flujo is None or st.session_state.get("flujo_cv_job") != job_id:
    st.stop()

# ---------- Pausa del Preguntón ----------
if flujo["esperando_respuestas"]:
    st.subheader("Antes de escribir, unas preguntas")
    st.caption(
        "Responde con la verdad: solo lo que confirmes con «Sí» puede aparecer en tu CV. "
        "Tus respuestas se guardan y no se vuelven a preguntar en otras ofertas."
    )
    with st.form("preguntas", border=False):
        for i, p in enumerate(flujo["preguntas"]):
            with st.container(border=True):
                tipo = "Obligatorio" if p.get("requirement_type") == "required" else "Deseable"
                with st.container(horizontal=True, gap="small"):
                    st.markdown(f"**{i + 1}. {p['tecnologia']}**")
                    st.badge(tipo, color="orange" if tipo == "Obligatorio" else "gray")
                st.caption(p["texto"])
                st.radio("¿Lo tienes?", ["No", "Sí"], key=f"tiene_{i}", horizontal=True)
                c1, c2 = st.columns([1, 2])
                c1.selectbox("Nivel (si es Sí)", ["basico", "intermedio", "avanzado"], key=f"nivel_{i}",
                             format_func=str.capitalize)
                c2.text_input("¿Dónde lo usaste? (si es Sí)", key=f"donde_{i}",
                              placeholder="Proyecto, trabajo o curso")
                st.text_input("¿Qué hiciste con eso? (opcional)", key=f"detalle_{i}")
        enviar = st.form_submit_button("Enviar respuestas y adaptar", type="primary")

    if enviar:
        respuestas = []
        for i, p in enumerate(flujo["preguntas"]):
            if st.session_state[f"tiene_{i}"] == "Sí":
                if not st.session_state[f"donde_{i}"].strip():
                    st.error(f"Indica dónde usaste {p['tecnologia']}, o marca «No».")
                    st.stop()
                respuestas.append({
                    "tecnologia": p["tecnologia"],
                    "la_tengo": True,
                    "nivel": st.session_state[f"nivel_{i}"],
                    "donde": st.session_state[f"donde_{i}"].strip(),
                    "detalle": st.session_state[f"detalle_{i}"].strip() or None,
                })
            else:
                respuestas.append({"tecnologia": p["tecnologia"], "la_tengo": False})

        with st.spinner("Pluma está adaptando tu CV..."):
            st.session_state["flujo_cv"] = consultar(services.responder_preguntas, flujo["thread_id"], respuestas)
        st.rerun()
    st.stop()

# ---------- Resultado ----------
if flujo["usa_texto_de_pluma"]:
    st.success("Tu CV está listo. Pluma lo adaptó y el validador lo aprobó.")
else:
    st.warning(
        "El texto adaptado no pasó el validador, así que el CV usa tus bullets originales "
        "ordenados por relevancia. El informe de brechas explica los motivos."
    )
    for aviso in flujo["avisos"]:
        st.caption(f"• {aviso}")

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
c1, c2 = st.columns(2)
for col, clave, etiqueta in ((c1, "ruta_cv", "Descargar CV"), (c2, "ruta_brechas", "Descargar brechas")):
    ruta = Path(flujo[clave])
    col.download_button(etiqueta, ruta.read_bytes(), file_name=ruta.name, mime=DOCX,
                        icon=":material/download:", use_container_width=True)
n_versiones = len(services.versiones_cv(job_id))
st.caption(
    f"Versión {n_versiones} para esta oferta, guardada en `{Path(flujo['ruta_cv']).parent}`. "
    "Las anteriores siguen disponibles en **Postulaciones**."
)
