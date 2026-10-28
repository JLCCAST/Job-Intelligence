"""
getonbrd.py

Fuente Get on Board (getonbrd.com), por su API pública v0:

    GET https://www.getonbrd.com/api/v0/search/jobs?query=...

No necesita clave y devuelve lo mismo que se ve en la web sin
iniciar sesión. Se consulta poco (una petición por búsqueda, una
vez al día) y con un User-Agent que identifica al proyecto.
"""

from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.fuentes import OfertaEncontrada

URL_BUSQUEDA = "https://www.getonbrd.com/api/v0/search/jobs"
NOMBRE_FUENTE = "Get on Board"
HEADERS = {"User-Agent": "Job-Intelligence/0.4 (proyecto personal; github.com/JLCCAST/Job-Intelligence)"}
TIMEOUT_SECONDS = 20
POR_PAGINA = 50

# Secciones de la oferta, en el orden en que se leen en la web.
SECCIONES = (
    ("description_headline", "description"),
    ("functions_headline", "functions"),
    ("desirable_headline", "desirable"),
    ("benefits_headline", "benefits"),
)


def _html_a_texto(html: Optional[str]) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "lxml").get_text("\n", strip=True)


def _empresa(atributos: dict) -> Optional[str]:
    return ((atributos.get("company") or {}).get("data") or {}).get("attributes", {}).get("name")


def convertir(item: dict) -> OfertaEncontrada:
    a = item["attributes"]
    empresa = _empresa(a)

    partes = [a["title"], f"Empresa: {empresa or 'no indicada'}", "Publicado en Get on Board."]
    if a.get("countries"):
        partes.append("Países: " + ", ".join(a["countries"]))
    if a.get("remote_modality"):
        partes.append(f"Modalidad: {a['remote_modality']}")
    if a.get("min_salary") or a.get("max_salary"):
        partes.append(f"Salario (USD/mes): {a.get('min_salary') or '?'} - {a.get('max_salary') or '?'}")
    for titulo, cuerpo in SECCIONES:
        texto = _html_a_texto(a.get(cuerpo))
        if texto:
            partes.append(f"\n{a.get(titulo) or ''}\n{texto}".rstrip())

    return OfertaEncontrada(
        fuente=NOMBRE_FUENTE,
        url=item["links"]["public_url"],
        titulo=a["title"],
        empresa=empresa,
        paises=a.get("countries") or [],
        remoto=bool(a.get("remote")),
        modalidad=a.get("remote_modality"),
        salario_min=a.get("min_salary"),
        salario_max=a.get("max_salary"),
        texto="\n".join(partes),
    )


def buscar(consulta: str) -> list[OfertaEncontrada]:
    """Una página de resultados (hasta 50). Lanza requests.RequestException si falla la red."""
    respuesta = requests.get(
        URL_BUSQUEDA,
        params={"query": consulta, "per_page": POR_PAGINA, "page": 1, "expand": '["company"]'},
        headers=HEADERS,
        timeout=TIMEOUT_SECONDS,
    )
    respuesta.raise_for_status()
    return [convertir(item) for item in respuesta.json().get("data", [])]
