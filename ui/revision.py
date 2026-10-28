import streamlit as st

from app import services
from ui.comun import plural, encabezado, escribir, leer

encabezado(
    "Revisión del catálogo",
    "Tecnologías que Archivero creó porque no existían en el catálogo y Gemini no estaba "
    "seguro (confianza < 0.75). Apruébalas si el nombre y la categoría son correctos.",
    seccion="Tú",
)

pendientes = leer("tecnologias_para_revisar")
if not pendientes:
    st.success("No hay tecnologías pendientes de revisión.")
    st.stop()

for t in pendientes:
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1.2], vertical_alignment="center")
    c1.markdown(f"**{t['tecnologia']}**")
    c2.write(t["categoria"].replace("_", " "))
    c3.write(plural(t['ofertas'], 'oferta', 'ofertas'))
    if c4.button("Aprobar", key=f"aprobar_{t['technology_id']}", icon=":material/check:"):
        escribir(services.aprobar_tecnologia, t["technology_id"])
        st.toast(f"{t['tecnologia']} aprobada.")
        st.rerun()

st.caption("Unir una tecnología con otra ya existente (como alias) llegará en una próxima versión.")
