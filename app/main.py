"""
main.py

API local. Solo traduce HTTP <-> capa de servicios; el flujo real lo
orquesta Batuta (app/agents/batuta.py):

    POST /analyze-job   texto o URL -> Lupa -> Archivero -> Balanza
    POST /recibir       lo envía el marcador "Enviar a Job-Intelligence"
                        desde el navegador; deja la oferta pendiente y
                        abre "Analizar oferta" con el texto prellenado.
"""

from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import pendientes
from app.schemas import AnalyzeJobRequest, AnalyzeJobResponse
from app.services import analizar_oferta

app = FastAPI(title="Job Analyzer API", version="0.4.0")

URL_APP = "http://localhost:8501"


@app.post("/analyze-job", response_model=AnalyzeJobResponse)
def analyze_job(request: AnalyzeJobRequest) -> AnalyzeJobResponse:
    # Con texto Y url se usa el texto pegado y la url queda como link
    # de la oferta (sirve para detectar duplicados y la fuente).
    url = str(request.url) if request.url else None
    return analizar_oferta(url=url, text=request.text)


@app.post("/recibir")
async def recibir(request: Request):
    """
    Recibe un formulario normal (no fetch): el navegador lo envía como
    una navegación, así no hacen falta reglas CORS. Se lee el cuerpo a
    mano para no depender de python-multipart.
    """
    cuerpo = (await request.body())[: pendientes.MAX_CARACTERES * 4].decode("utf-8", errors="replace")
    campos = parse_qs(cuerpo)
    texto = (campos.get("texto") or [""])[0]
    url = (campos.get("url") or [""])[0]
    if not texto.strip():
        return HTMLResponse("<p>No llegó texto de la oferta. Selecciona la descripción y vuelve a intentarlo.</p>",
                            status_code=400)
    id_ = pendientes.guardar(url, texto)
    return RedirectResponse(f"{URL_APP}/analizar?pendiente={id_}", status_code=303)
