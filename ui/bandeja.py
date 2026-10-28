import streamlit as st

from app import services
from ui.comun import plural, encabezado, escribir, leer, nivel_encaje, tarjeta_oferta

encabezado(
    "Bandeja",
    "Ofertas registradas que aún no revisas: las que trajo Sabueso de Get on Board y las que "
    "analizaste tú. Adapta tu CV a las que te interesen y descarta el resto.",
    seccion="Ofertas",
)

with st.container(horizontal=True, vertical_alignment="bottom"):
    filtro = st.segmented_control(
        "Encaje", ["Todos", "Encaje alto", "Encaje medio", "Encaje bajo"], default="Todos",
    )
    orden = st.segmented_control("Ordenar por", ["Match Score", "Más recientes"], default="Match Score")
    buscar = st.button("Buscar ofertas nuevas", icon=":material/travel_explore:")

if buscar:
    with st.spinner("Sabueso está buscando y Lupa analizando cada oferta nueva (puede tardar unos minutos)..."):
        r = escribir(services.buscar_ofertas_nuevas)
    st.success(
        f"Sabueso revisó {plural(r['encontradas'], 'oferta', 'ofertas')}: "
        f"{plural(len(r['registradas']), 'nueva registrada', 'nuevas registradas')}, "
        f"{r['ya_registradas']} ya estaban y {r['fuera_de_filtro']} no pasaron tu filtro.",
        icon=":material/travel_explore:",
    )
    if r["pendientes_por_tope"]:
        st.info(f"{plural(r['pendientes_por_tope'], 'oferta quedó', 'ofertas quedaron')} para la próxima búsqueda.")
    for error in r["errores"]:
        st.warning(error)

ofertas = leer("listar_ofertas")
bandeja = [o for o in ofertas if o["estado"] == "Registrada"]
if filtro and filtro != "Todos":
    bandeja = [o for o in bandeja if nivel_encaje(o["match_score"])[0] == filtro]
if orden == "Más recientes":
    bandeja.sort(key=lambda o: str(o["fecha_registro"]), reverse=True)
else:
    bandeja.sort(key=lambda o: o["match_score"] or 0, reverse=True)

if not bandeja:
    st.info("No hay ofertas en tu bandeja con ese filtro.", icon=":material/inbox:")
    st.stop()

st.caption(plural(len(bandeja), "oferta", "ofertas"))
for o in bandeja:
    acciones = tarjeta_oferta(o, mostrar_estado=False)
    if acciones.button("Adaptar mi CV", key=f"cv_{o['job_id']}", type="primary", icon=":material/edit_document:"):
        st.session_state["job_para_cv"] = o["job_id"]
        st.session_state.pop("flujo_cv", None)
        st.switch_page("ui/adaptar_cv.py")
    if acciones.button("Marcar como revisada", key=f"rev_{o['job_id']}", icon=":material/check:"):
        escribir(services.cambiar_estado, o["job_id"], "Analizada", "Revisada desde la bandeja")
        st.rerun()
    if acciones.button("Descartar", key=f"des_{o['job_id']}", icon=":material/delete:"):
        escribir(services.cambiar_estado, o["job_id"], "Descartada", "Descartada desde la bandeja")
        st.toast(f"Descartaste «{o['puesto']}».")
        st.rerun()
