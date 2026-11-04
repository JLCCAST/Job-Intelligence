"""
main.py

Servidor único de Job-Intelligence (http://localhost:8000):

    /api/...            API REST para el frontend (app/api.py)
    POST /analyze-job   texto o URL -> Lupa -> Archivero -> Balanza
    POST /recibir       lo envía el marcador "Enviar a Job-Intelligence"
                        desde el navegador; deja la oferta pendiente y
                        abre "Analizar oferta" con el texto prellenado.
    /                   el frontend React ya compilado (web/dist)
"""

import os
from urllib.parse import parse_qs

import psycopg2
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import pendientes
from app.api import router as api_router
from app.cv.cargador import RAIZ
from app.schemas import AnalyzeJobRequest, AnalyzeJobResponse
from app.services import analizar_oferta

app = FastAPI(title="Job-Intelligence API", version="0.5.0")
app.include_router(api_router)

# En desarrollo el frontend corre aparte con Vite (puerto 5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dónde redirigir después de recibir una oferta del marcador. Por defecto
# el mismo servidor (que sirve el frontend); con Vite en desarrollo se
# puede apuntar a http://localhost:5173.
URL_FRONTEND = os.environ.get("JI_URL_FRONTEND", "").rstrip("/")
CARPETA_WEB = RAIZ / "web" / "dist"


@app.exception_handler(psycopg2.OperationalError)
def supabase_caido(request: Request, exc: psycopg2.OperationalError):
    return JSONResponse(
        status_code=503,
        content={"detail": "No pude conectar con Supabase. Si el proyecto estuvo inactivo, "
                           "puede estar pausado: reactívalo en supabase.com."},
    )


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
    return RedirectResponse(f"{URL_FRONTEND}/analizar?pendiente={id_}", status_code=303)


# --------------------------------------------------------------
# Frontend compilado (web/dist). Va al final: las rutas de arriba
# tienen prioridad, y cualquier otra ruta devuelve index.html para
# que React Router la resuelva (/bandeja, /analizar, ...).
# --------------------------------------------------------------

if (CARPETA_WEB / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=CARPETA_WEB / "assets"), name="assets")


@app.get("/{ruta:path}", include_in_schema=False)
def frontend(ruta: str):
    archivo = (CARPETA_WEB / ruta).resolve()
    if ruta and archivo.is_file() and CARPETA_WEB.resolve() in archivo.parents:
        return FileResponse(archivo)
    indice = CARPETA_WEB / "index.html"
    if indice.is_file():
        return FileResponse(indice)
    return HTMLResponse(
        "<p>El frontend no está compilado. Ejecuta <code>python -m scripts.iniciar</code> "
        "(lo compila la primera vez) o <code>npm run build</code> dentro de <code>web/</code>.</p>",
        status_code=503,
    )
