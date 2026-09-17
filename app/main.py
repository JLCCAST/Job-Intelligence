"""
main.py

Endpoint POST /analyze-job. Encadena TODO el pipeline:

    texto pegado  ─┐
                   ├─> limpieza ─> Gemini ─> resolución de fuente ─> BD
    URL ─> scraper ┘

Este módulo NO tiene lógica propia de negocio: solo orquesta y
decide qué responder. Cada paso vive en su propio módulo.
"""

from fastapi import FastAPI

from app.cleaner import clean_html, normalize_whitespace
from app.gemini import extract_job_info
from app.repository import (
    buscar_job_por_url,
    calcular_y_guardar_match_score,
    insert_job_with_technologies,
)
from app.scraper import fetch_html
from app.schemas import AnalyzeJobRequest, AnalyzeJobResponse
from app.source_resolver import resolver_source

app = FastAPI(title="Job Analyzer API", version="0.2.0")

# Por debajo de esto, el texto limpio es sospechosamente corto:
# probablemente el cleaner no encontró la oferta real.
MIN_TEXTO_UTIL = 200


@app.post("/analyze-job", response_model=AnalyzeJobResponse)
def analyze_job(request: AnalyzeJobRequest) -> AnalyzeJobResponse:
    # ----------------------------------------------------------
    # PASO 1: conseguir el texto (Opción A: URL / Opción B: pegado)
    # ----------------------------------------------------------
    if request.text:
        # El texto pegado YA viene limpio (el usuario lo copió del
        # navegador renderizado), así que NO pasa por clean_html.
        origen = "manual_text"
        url = None
        raw_length = len(request.text)
        cleaned = normalize_whitespace(request.text)
    else:
        origen = "url"
        url = str(request.url)

        # Duplicado ANTES de Gemini: si ya la registramos, no tiene
        # sentido gastar cuota de la API para descartar el resultado.
        job_existente = buscar_job_por_url(url)
        if job_existente is not None:
            return AnalyzeJobResponse(
                source=origen,
                extraction_status="success",
                registration_status="duplicate",
                raw_length=0,
                job_id=job_existente,
                error_detail=(
                    f"Esa URL ya estaba registrada como job_id={job_existente}. "
                    "No se creó un job nuevo."
                ),
            )

        fetch_result = fetch_html(url)
        if not fetch_result.success:
            return AnalyzeJobResponse(
                source=origen,
                extraction_status="failed",
                registration_status="not_attempted",
                raw_length=0,
                error_detail=fetch_result.error,
            )

        raw_length = len(fetch_result.html)
        cleaned = clean_html(fetch_result.html)

    # Texto demasiado corto: se sigue intentando, pero queda marcado
    # como "partial" para que sepas que puede faltar contenido.
    estado_extraccion = "success" if len(cleaned) >= MIN_TEXTO_UTIL else "partial"

    # ----------------------------------------------------------
    # PASO 2: Gemini
    # ----------------------------------------------------------
    resultado_gemini = extract_job_info(cleaned)

    if not resultado_gemini.success:
        # Caso típico: 503 por saturación de la API. La oferta NO se
        # guarda; reintentar el mismo POST más tarde es seguro.
        return AnalyzeJobResponse(
            source=origen,
            extraction_status="failed",
            registration_status="not_attempted",
            raw_length=raw_length,
            cleaned_text=cleaned,
            error_detail=resultado_gemini.error,
        )

    extraction = resultado_gemini.data

    # ----------------------------------------------------------
    # PASO 3: oferta cerrada -> no se guarda
    # ----------------------------------------------------------
    if not extraction.is_offer_available:
        return AnalyzeJobResponse(
            source=origen,
            extraction_status=estado_extraccion,
            registration_status="offer_closed",
            raw_length=raw_length,
            cleaned_text=cleaned,
            extraction=extraction,
            error_detail="La oferta ya no está disponible, no se registró.",
        )

    # ----------------------------------------------------------
    # PASO 4: resolver fuente y guardar
    # ----------------------------------------------------------
    # Con URL manda el dominio (determinístico); sin URL, lo que
    # haya inferido Gemini del texto.
    source_name = resolver_source(url=url, source_name_gemini=extraction.source_name)

    resultado_insert = insert_job_with_technologies(
        extraction=extraction,
        source_name=source_name,
        url=url,
        descripcion_raw=None,
        descripcion_limpia=cleaned,
    )

    # ----------------------------------------------------------
    # PASO 5: Match Score (determinístico, sobre lo ya guardado)
    # ----------------------------------------------------------
    # Se calcula DESPUÉS del insert porque lee job_technology, que
    # recién existe una vez guardada la oferta.
    score = calcular_y_guardar_match_score(resultado_insert.job_id)

    return AnalyzeJobResponse(
        source=origen,
        extraction_status=estado_extraccion,
        registration_status="saved",
        match_score=score.score,
        cumple_ingles=score.cumple_ingles,
        tecnologias_faltantes=score.faltantes,
        requisitos_bajo_nivel=score.requisitos_bajo_nivel,
        raw_length=raw_length,
        cleaned_text=cleaned,
        extraction=extraction,
        job_id=resultado_insert.job_id,
        tecnologias_vinculadas=resultado_insert.tecnologias_vinculadas,
        tecnologias_creadas=resultado_insert.tecnologias_creadas,
        tecnologias_para_revisar=resultado_insert.tecnologias_para_revisar,
    )
