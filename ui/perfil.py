from typing import get_args

import pandas as pd
import streamlit as st

from app import services
from app.schemas import ExtractedTechnology
from ui.comun import encabezado, escribir, leer

CATEGORIAS = list(get_args(ExtractedTechnology.model_fields["category"].annotation))
NIVELES = ["basico", "intermedio", "avanzado"]

encabezado("Mi perfil", "Tus habilidades, tu CV base y lo que respondiste al Preguntón.", seccion="Tú")

tab_skills, tab_cv, tab_respuestas = st.tabs(["Habilidades", "CV base", "Respuestas al Preguntón"])

with tab_skills:
    st.caption(
        "Lo que Balanza compara contra cada oferta para calcular tu Match Score (tabla user_skill)."
    )
    perfil = leer("listar_mi_perfil")
    st.dataframe(
        pd.DataFrame(perfil),
        hide_index=True,
        column_config={
            "tecnologia": "Tecnología",
            "categoria": "Categoría",
            "nivel": "Nivel",
            "meses_experiencia": st.column_config.NumberColumn("Meses", format="%d"),
            "evidencia": "Evidencia",
        },
    )

    st.subheader("Agregar o actualizar una habilidad")
    with st.form("habilidad"):
        c1, c2, c3 = st.columns(3)
        nombre = c1.text_input("Tecnología", placeholder="Ej.: dbt")
        categoria = c2.selectbox("Categoría", CATEGORIAS, format_func=lambda c: c.replace("_", " "))
        nivel = c3.selectbox("Nivel", NIVELES, format_func=str.capitalize)
        c4, c5 = st.columns([1, 3])
        meses = c4.number_input("Meses de experiencia", min_value=0, step=1, value=0)
        evidencia = c5.text_input("Evidencia", placeholder="Dónde lo usaste: proyecto, trabajo o curso")
        guardar = st.form_submit_button("Guardar y recalcular scores", type="primary")

    if guardar:
        if not nombre.strip() or not evidencia.strip():
            st.error("Completa la tecnología y la evidencia: la evidencia es tu defensa contra inflar el perfil.")
        else:
            with st.spinner("Guardando y recalculando tus Match Score..."):
                escribir(services.guardar_habilidad, nombre.strip(), categoria, nivel, meses or None, evidencia.strip())
            st.toast(f"{nombre.strip()} guardado.")
            st.rerun()

with tab_cv:
    cv = services.cargar_cv_base()
    st.caption("Tu CV completo. Pluma solo puede usar lo que está aquí. Se edita en `data/cv_base.yaml`.")
    st.markdown(f"**{cv.contacto.nombre}** · {cv.contacto.email}")
    st.write(cv.perfil)

    c1, c2, c3 = st.columns(3)
    c1.metric("Experiencias", len(cv.experiencia))
    c2.metric("Proyectos", len(cv.proyectos))
    c3.metric("Habilidades declaradas", len(cv.skills_declaradas()))

    for p in cv.proyectos:
        with st.expander(p.nombre):
            for logro in p.logros:
                st.markdown(f"- {logro}")
            if p.stack:
                st.caption("Stack: " + " · ".join(p.stack))

with tab_respuestas:
    st.caption("Lo que respondiste al Preguntón. Se guarda en `data/respuestas.yaml`.")
    respuestas = services.cargar_respuestas()
    if respuestas:
        st.dataframe(
            pd.DataFrame([r.model_dump() for r in respuestas.values()]),
            hide_index=True,
            column_config={
                "tecnologia": "Tecnología",
                "la_tengo": st.column_config.CheckboxColumn("La tengo"),
                "nivel": "Nivel",
                "donde": "Dónde",
                "detalle": "Detalle",
            },
        )
    else:
        st.info("Todavía no has respondido preguntas.")
