"""
source_resolver.py

Responsabilidad única: dada la URL de una oferta, decidir a qué
fila del catálogo `source` corresponde.

Esto es 100% determinístico -- un dominio está en la lista o no
está. NO interviene el LLM: es justo el tipo de decisión que se
puede calcular, y calcularla evita que Gemini invente nombres de
portales que no existen en el catálogo.

El flujo de texto pegado (sin URL) NO usa este módulo; ahí la
fuente la infiere Gemini desde el texto.
"""

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit
from typing import Optional

# Dominio registrable -> nombre EXACTO de la fila en la tabla `source`.
# Si acá se escribe algo que no existe en el catálogo, se crearía una
# fila nueva y se fragmentaría el catálogo. Mantener sincronizado con
# el INSERT INTO source del schema y con el Literal de JobExtraction.
DOMINIO_A_SOURCE = {
    "linkedin.com": "LinkedIn",
    "indeed.com": "Indeed",
    "computrabajo.com": "Computrabajo",
    "computrabajo.com.pe": "Computrabajo",
    "bumeran.com": "Bumeran",
    "bumeran.com.pe": "Bumeran",
    # Fuente de Sabueso (API pública). Fila creada en sql/002_fuente_getonbrd.sql.
    "getonbrd.com": "Get on Board",
}

# Si hay URL pero el dominio no es de un portal conocido, en la
# práctica es el portal de empleos de la propia empresa (el caso
# Ferreyros / SAP SuccessFactors ya validado).
SOURCE_POR_DEFECTO_CON_URL = "Career Page"

# Fallback del flujo SIN URL (texto pegado), cuando Gemini tampoco
# pudo identificar el portal.
SOURCE_POR_DEFECTO_SIN_URL = "Otro"


def _extraer_hostname(url: str) -> Optional[str]:
    """
    Devuelve el hostname en minúsculas, sin `www.` y sin puerto.
    Devuelve None si la URL no es parseable o no tiene host.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    hostname = parsed.hostname  # ya viene sin puerto y en minúsculas
    if not hostname:
        return None

    if hostname.startswith("www."):
        hostname = hostname[len("www.") :]

    return hostname


def resolver_source_desde_url(url: str) -> str:
    """
    Mapea la URL a un nombre de `source` del catálogo.

    El match es por SUFIJO de dominio, porque un mismo portal usa
    varios hostnames (`linkedin.com`, `pe.linkedin.com`,
    `www.linkedin.com`). El punto en `"." + dominio` es
    intencional: sin él, `fakeindeed.com` daría falso positivo
    contra `indeed.com`.
    """
    hostname = _extraer_hostname(url)
    if hostname is None:
        return SOURCE_POR_DEFECTO_CON_URL

    for dominio, nombre_source in DOMINIO_A_SOURCE.items():
        if hostname == dominio or hostname.endswith("." + dominio):
            return nombre_source

    return SOURCE_POR_DEFECTO_CON_URL


def resolver_source(
    url: Optional[str],
    source_name_gemini: Optional[str],
) -> str:
    """
    Regla de precedencia única para todo el pipeline:

    1. Si hay URL -> manda el dominio (determinístico). Lo que haya
       dicho Gemini se ignora: el dominio es evidencia más fuerte
       que una mención dentro del texto.
    2. Si no hay URL -> se usa lo que infirió Gemini del texto.
    3. Si Gemini respondió 'no_especificado' (o nada) -> 'Otro'.
    """
    if url:
        return resolver_source_desde_url(url)

    if source_name_gemini and source_name_gemini != "no_especificado":
        return source_name_gemini

    return SOURCE_POR_DEFECTO_SIN_URL


_GETONBRD_EMPLEOS = re.compile(r"^https?://(www\.)?getonbrd\.com/empleos/[^/]+/([^/?#]+)")


def canonicalizar_url(url: Optional[str]) -> Optional[str]:
    """
    Una sola forma para la misma oferta, para que la detección de
    duplicados funcione venga de donde venga:

    - Get on Board: la API da `/jobs/<slug>` y el navegador termina en
      `/empleos/<categoría>/<slug>` (redirección). Se usa `/jobs/<slug>`.
    - Se quitan parámetros de seguimiento (`utm_*`, `trk`, `refId`...).
    - Se quita el `#...`, salvo en Computrabajo, donde identifica la oferta.
    """
    if not url:
        return url
    url = url.strip()
    m = _GETONBRD_EMPLEOS.match(url)
    if m:
        return f"https://www.getonbrd.com/jobs/{m.group(2)}"

    partes = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k not in _PARAMS_SEGUIMIENTO]
    # Computrabajo muestra la oferta elegida de una lista de resultados
    # solo con el fragmento (`/trabajo-de-...#<id>`): ahí el `#` ES la
    # oferta, y borrarlo haría que todas parezcan la misma.
    fragmento = partes.fragment if "computrabajo." in partes.netloc.lower() else ""
    return urlunsplit((partes.scheme, partes.netloc, partes.path.rstrip("/"), urlencode(query), fragmento))


_PARAMS_SEGUIMIENTO = {"trk", "trackingId", "refId", "ref", "src", "origin"}
