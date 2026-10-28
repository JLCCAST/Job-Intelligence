"""
main.py

Endpoint POST /analyze-job. Solo traduce HTTP <-> capa de servicios;
el flujo real lo orquesta Batuta (app/agents/batuta.py):

    texto pegado  ─┐
                   ├─> Lupa ─> Archivero ─> Balanza
    URL ───────────┘
"""

from fastapi import FastAPI

from app.schemas import AnalyzeJobRequest, AnalyzeJobResponse
from app.services import analizar_oferta

app = FastAPI(title="Job Analyzer API", version="0.3.0")


@app.post("/analyze-job", response_model=AnalyzeJobResponse)
def analyze_job(request: AnalyzeJobRequest) -> AnalyzeJobResponse:
    # Con texto Y url se usa el texto pegado y la url queda como link
    # de la oferta (sirve para detectar duplicados y la fuente).
    url = str(request.url) if request.url else None
    return analizar_oferta(url=url, text=request.text)
