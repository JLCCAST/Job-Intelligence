"""
scraper.py

Esta encargado de que cuando se le de una URL, intente traer el HTML crudo.
NO decide qué es relevante dentro del HTML (eso es trabajo de
cleaner.py) y NO lanza excepciones hacia el resto de la app --
siempre devuelve un FetchResult, éxito o fallo con motivo.
"""

from dataclasses import dataclass
from typing import Optional

import requests

# Ojo: No es para evadir protecciones serias como se puede encontrar en Bumeran, LinkedIn, etc.
# Para ello está la otra forma que es el fallback manual de enviar el texto. 

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

TIMEOUT_SECONDS = 10


@dataclass
class FetchResult:
    success: bool
    html: Optional[str] = None
    status_code: Optional[int] = None
    error: Optional[str] = None


def fetch_html(url: str) -> FetchResult:
    """
    Intenta obtener el HTML de `url`. Nunca lanza excepción --
    todos los casos de error quedan reflejados en FetchResult.error.
    """
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        return FetchResult(
            success=False,
            error=f"Timeout: el servidor no respondió en {TIMEOUT_SECONDS}s.",
        )
    except requests.exceptions.ConnectionError:
        return FetchResult(
            success=False,
            error="No se pudo conectar (dominio inválido, sin internet, DNS).",
        )
    except requests.exceptions.RequestException as exc:
        # Red de seguridad para cualquier otro error de la librería
        return FetchResult(success=False, error=f"Error de red: {exc}")

    if response.status_code != 200:
        return FetchResult(
            success=False,
            status_code=response.status_code,
            error=f"El servidor respondió con status {response.status_code}.",
        )

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return FetchResult(
            success=False,
            status_code=response.status_code,
            error=f"Contenido no es HTML (Content-Type: {content_type}).",
        )

    return FetchResult(
        success=True,
        html=response.text,
        status_code=response.status_code,
    )