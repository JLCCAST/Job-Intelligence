"""
main.py

Endpoint POST /analyze-job. Por ahora, la respuesta es solo
el resultado de extracción + limpieza.
"""

from fastapi import FastAPI

from app.cleaner import clean_html, normalize_whitespace
from app.scraper import fetch_html
from app.schemas import AnalyzeJobRequest, AnalyzeJobResponse

app = FastAPI(title="Job Analyzer API", version="0.1.0")


@app.post("/analyze-job", response_model=AnalyzeJobResponse)
def analyze_job(request: AnalyzeJobRequest) -> AnalyzeJobResponse:
    # Primero va la opcion B,  Solo normalizamos espacios.
    if request.text:
        cleaned = normalize_whitespace(request.text)
        return AnalyzeJobResponse(
            source="manual_text",
            extraction_status="success",
            raw_length=len(request.text),
            cleaned_text=cleaned,
        )

    # Opción A: hay URL, intentamos el camino automático.
    fetch_result = fetch_html(str(request.url))

    if not fetch_result.success:
        return AnalyzeJobResponse(
            source="url",
            extraction_status="failed",
            raw_length=0,
            error_detail=fetch_result.error,
        )

    cleaned = clean_html(fetch_result.html)

    # Si el texto limpio quedó muy corto, lo marcamos "partial" en vez de "success" (revisión manual)
    status = "success" if len(cleaned) >= 200 else "partial"

    return AnalyzeJobResponse(
        source="url",
        extraction_status=status,
        raw_length=len(fetch_result.html),
        cleaned_text=cleaned,
    )