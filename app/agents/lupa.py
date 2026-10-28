"""
lupa.py -- agente Lupa

Tarea fija: conseguir el texto de la oferta y extraer sus requisitos
con Gemini. Tiene dos nodos en el grafo:

    leer_oferta  : texto pegado o URL -> texto limpio
    extraer      : texto limpio -> JobExtraction (Gemini)

No guarda nada en la BD: eso es trabajo del Archivero.
"""

from app.cleaner import clean_html, normalize_whitespace
from app.gemini import extract_job_info
from app.repository import buscar_job_por_url
from app.scraper import fetch_html
from app.source_resolver import canonicalizar_url
from app.agents.estado import OfertaState

# Por debajo de esto, el texto limpio es sospechosamente corto:
# probablemente el cleaner no encontró la oferta real.
MIN_TEXTO_UTIL = 200


def leer_oferta(state: OfertaState) -> OfertaState:
    # Misma oferta = mismo link, aunque llegue por la API o por el navegador.
    url = canonicalizar_url(state.get("url"))
    texto = state.get("text")

    if texto and not url:
        # El texto pegado YA viene limpio (el usuario lo copió del
        # navegador renderizado), así que NO pasa por clean_html.
        cleaned = normalize_whitespace(texto)
        return _texto_listo("manual_text", len(texto), cleaned, url=None)

    # Con texto Y url (texto pegado con su link, o lo que trae Sabueso
    # de una API) no se descarga nada: la URL sirve para detectar
    # duplicados y para resolver la fuente por dominio.
    origen = state.get("origen") or ("manual_text" if texto else "url")

    # Duplicado ANTES de Gemini: si ya la registramos, no tiene
    # sentido gastar cuota de la API para descartar el resultado.
    job_existente = buscar_job_por_url(url)
    if job_existente is not None:
        return {
            "terminado": True,
            "source": origen,
            "extraction_status": "success",
            "registration_status": "duplicate",
            "raw_length": 0,
            "job_id": job_existente,
            "error_detail": (
                f"Esa URL ya estaba registrada como job_id={job_existente}. "
                "No se creó un job nuevo."
            ),
        }

    if texto:
        return _texto_listo(origen, len(texto), normalize_whitespace(texto), url=url)

    fetch_result = fetch_html(url)
    if not fetch_result.success:
        return {
            "terminado": True,
            "source": "url",
            "extraction_status": "failed",
            "registration_status": "not_attempted",
            "raw_length": 0,
            "error_detail": fetch_result.error,
        }

    return _texto_listo("url", len(fetch_result.html), clean_html(fetch_result.html), url=url)


def _texto_listo(origen: str, raw_length: int, cleaned: str, url) -> OfertaState:
    # Texto demasiado corto: se sigue intentando, pero queda marcado
    # como "partial" para que sepas que puede faltar contenido.
    estado = "success" if len(cleaned) >= MIN_TEXTO_UTIL else "partial"
    return {
        "terminado": False,
        "url": url,
        "source": origen,
        "raw_length": raw_length,
        "cleaned_text": cleaned,
        "extraction_status": estado,
    }


def extraer(state: OfertaState) -> OfertaState:
    resultado = extract_job_info(state["cleaned_text"])

    if not resultado.success:
        # Caso típico: 503 por saturación de la API. La oferta NO se
        # guarda; reintentar más tarde es seguro.
        return {
            "terminado": True,
            "extraction_status": "failed",
            "registration_status": "not_attempted",
            "error_detail": resultado.error,
        }

    extraction = resultado.data
    if not extraction.is_offer_available:
        return {
            "terminado": True,
            "extraction": extraction,
            "registration_status": "offer_closed",
            "error_detail": "La oferta ya no está disponible, no se registró.",
        }

    return {"extraction": extraction}
