import pandas as pd
import streamlit as st

from app import services
from ui.comun import ANCHO_INDICADOR, encabezado, escribir, formato_score, nivel_encaje

encabezado(
    "Analizar oferta",
    "Lupa extrae los requisitos, Archivero la guarda y Balanza calcula qué tanto encajas.",
    seccion="Ofertas",
)

modo = st.radio("¿Cómo traes la oferta?", ["Pegar texto", "URL"], horizontal=True)
if modo == "URL":
    st.caption(
        "LinkedIn, Indeed, Computrabajo y Bumeran no se pueden leer por URL: "
        "para esos portales copia el texto de la oferta y pégalo."
    )

with st.form("analizar"):
    if modo == "URL":
        url = st.text_input("URL de la oferta", placeholder="https://...")
        texto = None
    else:
        texto = st.text_area("Texto de la oferta", height=280, placeholder="Pega aquí la descripción completa")
        url = st.text_input(
            "Link de la oferta (opcional)",
            placeholder="https://www.linkedin.com/jobs/view/...",
            help="Se guarda para abrir la oferta después, detectar si ya la registraste "
                 "y saber de qué portal viene. No se descarga: se usa el texto que pegaste.",
        )
    enviar = st.form_submit_button("Analizar", type="primary")

if enviar:
    url = (url or "").strip()
    if modo == "URL" and not url:
        st.error("Escribe la URL de la oferta.")
        st.stop()
    if modo == "Pegar texto" and not (texto or "").strip():
        st.error("Pega el texto de la oferta.")
        st.stop()
    if url and not url.startswith(("http://", "https://")):
        st.error("El link debe empezar con http:// o https://")
        st.stop()
    with st.spinner("Analizando la oferta..."):
        st.session_state["ultimo_analisis"] = escribir(
            services.analizar_oferta, url=(url or None), text=(texto or None)
        )

r = st.session_state.get("ultimo_analisis")
if r is None:
    st.stop()

MENSAJES = {
    "saved": ("success", "Oferta registrada."),
    "duplicate": ("info", "Esa URL ya estaba registrada; muestro la oferta existente."),
    "offer_closed": ("warning", "La oferta ya no está disponible, así que no se registró."),
    "not_attempted": ("error", "No se pudo analizar la oferta."),
}
tipo, mensaje = MENSAJES[r.registration_status]
getattr(st, tipo)(mensaje + (f" {r.error_detail}" if r.error_detail and tipo != "success" else ""))

if r.extraction_status == "partial":
    st.warning("El texto extraído es muy corto: puede faltar parte de la oferta. Si es así, pega el texto a mano.")

if r.extraction:
    e = r.extraction
    st.subheader(e.job_title)
    texto, color, icono = nivel_encaje(r.match_score)
    st.badge(texto, color=color, icon=icono)
    with st.container(horizontal=True, gap="small"):
        st.metric("Match Score", formato_score(r.match_score), border=True, icon=":material/target:",
                  width=ANCHO_INDICADOR)
        st.metric("Empresa", e.company_name.replace("no_especificado", "No especificada"), border=True,
                  icon=":material/apartment:", width=ANCHO_INDICADOR)
        st.metric("Área", e.area.replace("_", " "), border=True, icon=":material/category:",
                  width=ANCHO_INDICADOR)
        st.metric("Inglés", e.english_level.replace("no_especificado", "No pide").capitalize(), border=True,
                  icon=":material/translate:", width=ANCHO_INDICADOR)

    if r.cumple_ingles is False:
        st.warning("Tu nivel de inglés está por debajo del pedido.")
    if r.requisitos_bajo_nivel:
        st.warning("Obligatorios donde estás por debajo del nivel pedido: " + ", ".join(r.requisitos_bajo_nivel))
    if r.tecnologias_faltantes:
        st.error("Te falta: " + ", ".join(r.tecnologias_faltantes))

    st.markdown("**Requisitos que encontró Lupa**")
    st.dataframe(
        pd.DataFrame([t.model_dump() for t in e.technologies]),
        hide_index=True,
        column_config={
            "name": "Tecnología",
            "category": "Categoría",
            "requirement_type": "Tipo",
            "level": "Nivel pedido",
            "confidence": st.column_config.NumberColumn("Confianza", format="%.2f"),
            "evidence_text": "Evidencia en la oferta",
        },
    )

if r.tecnologias_para_revisar:
    st.info("Tecnologías nuevas para revisar en el catálogo: " + ", ".join(r.tecnologias_para_revisar))

if r.job_id and r.registration_status in ("saved", "duplicate"):
    if st.button("Adaptar mi CV a esta oferta", type="primary", icon=":material/description:"):
        st.session_state["job_para_cv"] = r.job_id
        st.session_state.pop("flujo_cv", None)
        st.switch_page("ui/adaptar_cv.py")
