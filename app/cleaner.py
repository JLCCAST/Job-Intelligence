"""
cleaner.py

Responsabilidad única: recibir HTML crudo (de donde sea que haya
venido -- scraper.py o texto pegado manualmente) y devolver texto
plano con el contenido relevante, sin ruido de navegación/scripts.

No es perfecto -- es una heurística. El texto que produce todavía
puede tener algo de ruido, y por eso Gemini (Fase 4) recibe este
texto sabiendo que puede no estar 100% limpio.
"""

import re
from bs4 import BeautifulSoup

# Etiquetas que casi nunca contienen la oferta en sí -- se eliminan
# sin heurística, de forma determinística.
NOISE_TAGS = ["script", "style", "nav", "footer", "header", "form", "iframe", "noscript"]

# Palabras que, si aparecen en el id o class de un elemento, indican
# que es ruido (banners de cookies, modales de consentimiento, etc.)
# -- no depende de ningún sitio en particular, son convenciones
# comunes en la web.
NOISE_ID_CLASS_KEYWORDS = ["cookie", "consent", "gdpr", "modal", "banner"]

# Roles ARIA que sindican secciones que NO son el contenido principal.
NOISE_ARIA_ROLES = ["navigation", "banner", "contentinfo", "search", "complementary"]

# Etiquetas semánticas en las que confiamos primero, si el sitio las usa.
SEMANTIC_CONTENT_TAGS = ["main", "article"]

# Si el contenido semántico encontrado es más corto que esto,
# no confiamos en él y caemos a la heurística de bloque más largo
MIN_SEMANTIC_LENGTH = 200

# Piso mucho más bajo para el Paso 2b 
MIN_HEURISTIC_LENGTH = 40


def normalize_whitespace(text: str) -> str:
    """
    Colapsa espacios/saltos de línea repetidos.

    Pública a propósito: main.py también la usa directo sobre el
    texto pegado manualmente (Opción B), que YA es texto limpio
    (el usuario lo copió del navegador renderizado, no del HTML
    fuente) y por lo tanto NO debe pasar por clean_html().
    """
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _es_ruido_por_atributos(tag) -> bool:
    """
    Revisa si el id/class de un tag contiene alguna palabra de
    NOISE_ID_CLASS_KEYWORDS. Genérico -- no depende del sitio.
    """
    id_valor = (tag.get("id") or "").lower()
    clases = " ".join(tag.get("class") or []).lower()
    texto_atributos = f"{id_valor} {clases}"
    return any(keyword in texto_atributos for keyword in NOISE_ID_CLASS_KEYWORDS)


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    # Paso 1: limpieza determinística por tipo de etiqueta.
    for tag_name in NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Paso 1b: limpieza por id/class sospechoso (cookies, modales)
    for tag in soup.find_all(True):
        if tag.parent is None:
            continue  # ya fue eliminado por un decompose() anterior
        es_rol_ruido = (tag.get("role") or "").lower() in NOISE_ARIA_ROLES
        if tag.name == "table" or _es_ruido_por_atributos(tag) or es_rol_ruido:
            tag.decompose()

    # Paso 2a: confiar en etiquetas semánticas (<main>/<article>) 
    semantic_blocks = soup.find_all(SEMANTIC_CONTENT_TAGS)
    semantic_blocks += soup.find_all(attrs={"role": "main"})
    if semantic_blocks:
        text = "\n\n".join(
            block.get_text(separator="\n", strip=True) for block in semantic_blocks
        )
        if len(text) >= MIN_SEMANTIC_LENGTH:
            return normalize_whitespace(text)

    # Paso 2b: heurística de "bloque de texto más largo" como fallback.
    candidates = soup.find_all(["div", "section"])
    best_block = None
    best_length = 0
    for block in candidates:
        block_text = block.get_text(strip=True)
        if len(block_text) > best_length:
            best_length = len(block_text)
            best_block = block

    if best_block is not None and best_length >= MIN_HEURISTIC_LENGTH:
        return normalize_whitespace(best_block.get_text(separator="\n", strip=True))

    # Último recurso: todo el texto del body. 
    body = soup.find("body")
    fallback_text = body.get_text(separator="\n", strip=True) if body else soup.get_text()
    return normalize_whitespace(fallback_text)