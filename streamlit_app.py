"""
App local de Job-Intelligence.

    streamlit run streamlit_app.py

Solo interfaz: todo lo que hace pasa por app/services.py, así se
puede reemplazar por un frontend HTML sin tocar la lógica.
"""

import streamlit as st

from ui.comun import api_activa, estilos

st.set_page_config(page_title="Job-Intelligence", page_icon="assets/icono.svg", layout="wide")
st.logo("assets/logo.svg", icon_image="assets/icono.svg", size="large")
estilos()

paginas = {
    "": [
        st.Page("ui/inicio.py", title="Inicio", icon=":material/space_dashboard:", default=True),
    ],
    "Ofertas": [
        st.Page("ui/bandeja.py", title="Bandeja", icon=":material/inbox:"),
        st.Page("ui/analizar.py", title="Analizar oferta", icon=":material/document_search:"),
        st.Page("ui/postulaciones.py", title="Postulaciones", icon=":material/work:"),
        st.Page("ui/adaptar_cv.py", title="Adaptar CV", icon=":material/edit_document:"),
    ],
    "Tú": [
        st.Page("ui/perfil.py", title="Mi perfil", icon=":material/person:"),
        st.Page("ui/que_estudiar.py", title="Qué estudiar", icon=":material/explore:"),
        st.Page("ui/analisis.py", title="Análisis", icon=":material/insights:"),
        st.Page("ui/revision.py", title="Revisión del catálogo", icon=":material/rule:"),
    ],
}

pagina = st.navigation(paginas)
with st.sidebar:
    if api_activa():
        st.caption(":material/check_circle: Marcador del navegador listo")
    else:
        st.caption(":material/power_off: Marcador apagado: abre la app con `python -m scripts.iniciar`")
    st.caption("Datos en tu PC y en tu Supabase · Gemini, plan gratuito")
pagina.run()
