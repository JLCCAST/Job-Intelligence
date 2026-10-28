import altair as alt
import pandas as pd
import streamlit as st

from app import services
from ui.comun import plural, encabezado, leer

# Slots 1 y 2 de la paleta categórica validada (azul / naranja).
COLOR_LA_TIENES = "#2a78d6"
COLOR_TE_FALTA = "#eb6834"
MUESTRA_MINIMA = 10

encabezado("Análisis de tus ofertas", "Qué te piden más y cuánto de eso ya cubres.", seccion="Tú")

ofertas = leer("listar_ofertas")
demanda = leer("demanda_tecnologias")

if not demanda:
    st.info("Aún no hay requisitos registrados. Analiza ofertas para ver qué te piden más.")
    st.stop()

if len(ofertas) < MUESTRA_MINIMA:
    st.warning(
        f"Calculado con solo {plural(len(ofertas), 'oferta', 'ofertas')}. Con menos de {MUESTRA_MINIMA} "
        "los resultados son orientativos, no una tendencia."
    )

df = pd.DataFrame(demanda)
df["estado"] = df["la_tengo"].map({True: "La tienes", False: "Te falta"})

total_pedidos = int(df["total"].sum())
cubiertos = int(df.loc[df["la_tengo"], "total"].sum())
obligatorias_faltantes = df[(~df["la_tengo"]) & (df["obligatoria"] > 0)]

c1, c2, c3 = st.columns(3)
c1.metric("Ofertas analizadas", len(ofertas))
c2.metric("Requisitos que cubres", f"{cubiertos / total_pedidos:.0%}",
          help="Sobre todas las veces que una oferta pidió una tecnología")
c3.metric("Obligatorias que te faltan", len(obligatorias_faltantes))

st.subheader("¿Qué te piden más?")
top = df.head(15)
grafico = (
    alt.Chart(top)
    .mark_bar(cornerRadiusEnd=4)
    .encode(
        x=alt.X("total:Q", title="Ofertas que la piden", axis=alt.Axis(tickMinStep=1, grid=True)),
        y=alt.Y("tecnologia:N", sort="-x", title=None, scale=alt.Scale(paddingInner=0.3)),
        color=alt.Color(
            "estado:N",
            title=None,
            scale=alt.Scale(domain=["La tienes", "Te falta"], range=[COLOR_LA_TIENES, COLOR_TE_FALTA]),
            legend=alt.Legend(orient="top"),
        ),
        tooltip=[
            alt.Tooltip("tecnologia:N", title="Tecnología"),
            alt.Tooltip("obligatoria:Q", title="Obligatoria en"),
            alt.Tooltip("deseable:Q", title="Deseable en"),
            alt.Tooltip("estado:N", title="Estado"),
        ],
    )
    .properties(height=alt.Step(28))
)
st.altair_chart(grafico, use_container_width=True)

with st.expander("Ver como tabla"):
    st.dataframe(
        df[["tecnologia", "categoria", "obligatoria", "deseable", "total", "estado"]],
        hide_index=True,
        column_config={
            "tecnologia": "Tecnología",
            "categoria": "Categoría",
            "obligatoria": "Obligatoria",
            "deseable": "Deseable",
            "total": "Total",
            "estado": "Estado",
        },
    )

if not obligatorias_faltantes.empty:
    st.subheader("Tus brechas obligatorias más frecuentes")
    for _, fila in obligatorias_faltantes.head(5).iterrows():
        st.markdown(f"- **{fila['tecnologia']}**: obligatoria en {plural(int(fila['obligatoria']), 'oferta', 'ofertas')}")
