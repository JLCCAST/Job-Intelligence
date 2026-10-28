"""
Utilidades y componentes visuales compartidos por las páginas.

Los colores vienen del tema (.streamlit/config.toml); el CSS de aquí
solo ajusta espaciado y tipografía, y usa transparencias para verse
bien en modo claro y oscuro.
"""

from datetime import datetime
from typing import Optional

import psycopg2
import streamlit as st

ESTADOS_ACTIVOS = ("Postulada", "Entrevista", "Oferta")

_CSS = """
<style>
  .block-container { padding-top: 3.6rem; max-width: 1180px; }
  [data-testid="stSidebarNav"] a span { font-weight: 500; }
  .ji-eyebrow { font-size: .78rem; font-weight: 600; letter-spacing: .08em;
                text-transform: uppercase; opacity: .6; margin-bottom: .1rem; }
  .ji-titulo { font-family: "Plus Jakarta Sans", Inter, sans-serif; font-size: 2rem;
               font-weight: 800; line-height: 1.15; margin: 0 0 .35rem 0; }
  .ji-desc { font-size: 1rem; opacity: .72; margin: 0 0 1.4rem 0; max-width: 60ch; }
  .ji-hero { background: #2a78d6; color: #fff; border-radius: 1rem;
             padding: 1.6rem 1.8rem; margin-bottom: 1.2rem; }
  .ji-hero h2 { color: #fff; font-family: "Plus Jakarta Sans", Inter, sans-serif;
                font-size: 1.7rem; font-weight: 800; margin: 0 0 .35rem 0; padding: 0; }
  .ji-hero p { color: rgba(255,255,255,.88); margin: 0; font-size: 1rem; }
  .ji-hero .ji-fecha { font-size: .8rem; font-weight: 600; letter-spacing: .06em;
                       text-transform: uppercase; color: rgba(255,255,255,.75); margin-bottom: .4rem; }
  .ji-puesto { font-weight: 650; font-size: 1.02rem; line-height: 1.3; margin: 0; }
  .ji-meta { font-size: .86rem; opacity: .65; margin: .15rem 0 .45rem 0; }
  .ji-score { font-family: "Plus Jakarta Sans", Inter, sans-serif; font-weight: 800;
              font-size: 1.6rem; line-height: 1; text-align: right; }
  .ji-score small { display: block; font-size: .72rem; font-weight: 600; opacity: .6;
                    letter-spacing: .04em; text-transform: uppercase; margin-top: .25rem; }
</style>
"""


def estilos() -> None:
    st.html(_CSS)


def consultar(funcion, *args, **kwargs):
    """
    Llama a un servicio y, si Supabase no responde, muestra un
    mensaje claro y detiene la página en vez de un traceback.
    """
    try:
        return funcion(*args, **kwargs)
    except psycopg2.OperationalError as exc:
        st.error(
            "No pude conectar con Supabase. Si el proyecto estuvo inactivo, "
            "puede estar pausado: reactívalo en supabase.com y recarga la página.",
            icon=":material/cloud_off:",
        )
        with st.expander("Detalle técnico"):
            st.code(str(exc))
        st.stop()


def _html(texto: Optional[str]) -> str:
    from html import escape
    return escape(texto or "")


# --------------------------------------------------------------
# Encabezados
# --------------------------------------------------------------

def encabezado(titulo: str, descripcion: Optional[str] = None, seccion: Optional[str] = None) -> None:
    partes = []
    if seccion:
        partes.append(f'<div class="ji-eyebrow">{_html(seccion)}</div>')
    partes.append(f'<div class="ji-titulo">{_html(titulo)}</div>')
    if descripcion:
        partes.append(f'<p class="ji-desc">{_html(descripcion)}</p>')
    st.html("".join(partes))


def hero(titulo: str, texto: str, fecha: str) -> None:
    st.html(
        f'<div class="ji-hero"><div class="ji-fecha">{_html(fecha)}</div>'
        f"<h2>{_html(titulo)}</h2><p>{_html(texto)}</p></div>"
    )


# --------------------------------------------------------------
# Match Score
# --------------------------------------------------------------

def nivel_encaje(score: Optional[float]) -> tuple[str, str, str]:
    """(texto, color de st.badge, icono). El texto acompaña siempre al color."""
    if score is None:
        return "Sin score", "gray", ":material/help:"
    if score >= 75:
        return "Encaje alto", "green", ":material/trending_up:"
    if score >= 50:
        return "Encaje medio", "orange", ":material/trending_flat:"
    return "Encaje bajo", "red", ":material/trending_down:"


def formato_score(score: Optional[float]) -> str:
    return f"{score:.1f}%" if score is not None else "—"


def etiqueta_oferta(o: dict) -> str:
    score = f"{o['match_score']:.0f}%" if o.get("match_score") is not None else "sin score"
    return f"{o['puesto']} — {o['empresa']} ({score})"


def _fecha_corta(valor) -> Optional[str]:
    if not valor:
        return None
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor)
        except ValueError:
            return None
    return valor.strftime("%d/%m/%Y")


def tarjeta_oferta(o: dict, mostrar_estado: bool = True):
    """
    Tarjeta de una oferta. Devuelve un contenedor horizontal debajo de
    la tarjeta donde la página pone sus botones de acción.
    """
    caja = st.container(border=True)
    with caja:
        izq, der = st.columns([5, 1.2], vertical_alignment="center")
        meta = " · ".join(x for x in (o.get("empresa"), o.get("fuente"), _fecha_corta(o.get("fecha_registro"))) if x)
        izq.html(f'<p class="ji-puesto">{_html(o["puesto"])}</p><p class="ji-meta">{_html(meta)}</p>')
        with izq.container(horizontal=True, gap="small"):
            texto, color, icono = nivel_encaje(o.get("match_score"))
            st.badge(texto, color=color, icon=icono)
            if mostrar_estado and o.get("estado"):
                st.badge(o["estado"], color="gray", icon=":material/flag:")
            if o.get("url"):
                st.markdown(f"[Ver oferta]({o['url']})")
        der.html(
            f'<div class="ji-score">{formato_score(o.get("match_score"))}<small>Match Score</small></div>'
        )
        acciones = st.container(horizontal=True, gap="small")
    return acciones


# --------------------------------------------------------------
# Accesos y pasos
# --------------------------------------------------------------

def acceso(pagina: str, titulo: str, descripcion: str, icono: str) -> None:
    with st.container(border=True, width=ANCHO_INDICADOR):
        st.page_link(pagina, label=titulo, icon=icono)
        st.caption(descripcion)


def pasos(nombres: list[str], actual: int) -> None:
    """Indicador de progreso: hecho (verde), actual (primario), pendiente (gris)."""
    with st.container(horizontal=True, gap="small"):
        for i, nombre in enumerate(nombres):
            if i < actual:
                st.badge(f"{i + 1}. {nombre}", color="green", icon=":material/check:")
            elif i == actual:
                st.badge(f"{i + 1}. {nombre}", color="primary", icon=":material/radio_button_checked:")
            else:
                st.badge(f"{i + 1}. {nombre}", color="gray")


# --------------------------------------------------------------
# Lecturas en caché
# --------------------------------------------------------------
# Cada consulta abre una conexión a Supabase (~1 s). Las lecturas se
# guardan 2 minutos; cualquier escritura hecha desde la app limpia la
# caché, así lo que ves siempre refleja tus propios cambios.

@st.cache_data(ttl=120, show_spinner=False)
def _lectura_cacheada(nombre: str, args: tuple):
    from app import services
    return getattr(services, nombre)(*args)


def leer(nombre: str, *args):
    """Lectura de app.services por nombre, con caché. Ej.: leer("listar_ofertas")."""
    return consultar(_lectura_cacheada, nombre, args)


def escribir(funcion, *args, **kwargs):
    """Llama a un servicio que cambia datos y limpia la caché de lecturas."""
    resultado = consultar(funcion, *args, **kwargs)
    _lectura_cacheada.clear()
    return resultado


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"

# Ancho fijo de los indicadores: así se acomodan en filas en vez de cortarse.
ANCHO_INDICADOR = 230


# Marcador del navegador ("bookmarklet"). Envía la selección (o toda la
# página) y el link a la API local con un formulario normal: es una
# navegación, no un fetch, así que no necesita CORS. Abre la app en la
# misma pestaña (con target=_blank algunos navegadores lo convierten en
# GET y se pierde el texto); para volver a la oferta: atrás.
MARCADOR = (
    "javascript:(()=>{const f=document.createElement('form');f.method='POST';"
    "f.action='http://localhost:8000/recibir';"
    "const t=(String(window.getSelection())||document.body.innerText).slice(0,60000);"
    "[['url',location.href],['texto',t]].forEach(([n,v])=>{const i=document.createElement('input');"
    "i.type='hidden';i.name=n;i.value=v;f.appendChild(i)});"
    "document.body.appendChild(f);f.submit()})()"
)


@st.cache_data(ttl=15, show_spinner=False)
def api_activa() -> bool:
    """¿Está corriendo la API que recibe las ofertas del marcador (puerto 8000)?"""
    import requests

    try:
        return requests.get("http://127.0.0.1:8000/docs", timeout=0.5).ok
    except requests.RequestException:
        return False


def aviso_api_apagada() -> None:
    st.warning(
        "La API que recibe las ofertas del marcador no está corriendo, así que el botón del navegador "
        "dará «No se puede acceder a este sitio». Cierra la app y ábrela con "
        "`python -m scripts.iniciar`, que levanta la app y la API juntas.",
        icon=":material/power_off:",
    )
