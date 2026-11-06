"""
api.py

Endpoints REST (JSON) bajo /api para el frontend en React (web/).
Solo traducen HTTP <-> app/services.py: la lógica sigue en los
agentes, así que cambiar de interfaz no tocó nada del backend.
"""

from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import pendientes, services
from app.cv.cargador import RAIZ, guardar_cv_base
from app.cv.modelo import CVBase

router = APIRouter(prefix="/api")

CARPETA_SALIDAS = (RAIZ / "salidas").resolve()
NIVELES = Literal["basico", "intermedio", "avanzado"]


# --------------------------------------------------------------
# Inicio y ofertas
# --------------------------------------------------------------

@router.get("/inicio")
def inicio():
    try:
        nombre = services.cargar_cv_base().contacto.nombre.split()[0].capitalize()
    except services.CVBaseNoEncontrado:
        nombre = None
    return {
        "nombre": nombre,
        "ofertas": services.listar_ofertas(),
        "resumen": services.resumen_centinela(),
        "por_revisar": len(services.tecnologias_para_revisar()),
    }


@router.get("/ofertas")
def ofertas():
    return services.listar_ofertas()


@router.get("/estados")
def estados():
    return services.listar_estados()


class CambioEstado(BaseModel):
    estado: str
    nota: Optional[str] = None


@router.post("/ofertas/{job_id}/estado")
def cambiar_estado(job_id: int, cambio: CambioEstado):
    if cambio.estado not in services.listar_estados():
        raise HTTPException(400, f"Estado desconocido: {cambio.estado}")
    services.cambiar_estado(job_id, cambio.estado, (cambio.nota or "").strip() or None)
    return {"ok": True}


@router.get("/ofertas/{job_id}/historial")
def historial(job_id: int):
    return services.historial_estados(job_id)


@router.get("/ofertas/{job_id}/cvs")
def versiones_cv(job_id: int):
    return services.versiones_cv(job_id)


class PedidoAnalisis(BaseModel):
    url: Optional[str] = None
    texto: Optional[str] = None


@router.post("/analizar")
def analizar(pedido: PedidoAnalisis):
    url = (pedido.url or "").strip() or None
    texto = (pedido.texto or "").strip() or None
    if not url and not texto:
        raise HTTPException(400, "Envía la URL o el texto de la oferta.")
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(400, "El link debe empezar con http:// o https://")
    return services.analizar_oferta(url=url, text=texto)


@router.post("/sabueso/buscar")
def buscar_ofertas():
    return services.buscar_ofertas_nuevas()


@router.get("/pendientes/{id_}")
def tomar_pendiente(id_: str):
    oferta = pendientes.tomar(id_)
    if oferta is None:
        raise HTTPException(404, "La oferta enviada ya se abrió o no existe.")
    return oferta


# --------------------------------------------------------------
# Adaptar CV
# --------------------------------------------------------------

@router.post("/cv/{job_id}/iniciar")
def iniciar_cv(job_id: int):
    try:
        services.cargar_cv_base()
    except services.CVBaseNoEncontrado as exc:
        raise HTTPException(400, str(exc))
    return services.iniciar_adaptacion_cv(job_id)


class Respuesta(BaseModel):
    tecnologia: str
    la_tengo: bool
    nivel: Optional[NIVELES] = None
    donde: Optional[str] = None
    detalle: Optional[str] = None


@router.post("/cv/flujos/{thread_id}/responder")
def responder(thread_id: str, respuestas: list[Respuesta]):
    for r in respuestas:
        if r.la_tengo and not (r.donde or "").strip():
            raise HTTPException(400, f"Indica dónde usaste {r.tecnologia}, o marca que no lo tienes.")
    try:
        return services.responder_preguntas(thread_id, [r.model_dump(exclude_none=True) for r in respuestas])
    except services.FlujoNoEspera as exc:
        raise HTTPException(409, str(exc))


class Revision(BaseModel):
    rechazados: list[str] = []  # ids de los cambios de la IA que no quieres


@router.post("/cv/flujos/{thread_id}/revisar")
def revisar(thread_id: str, revision: Revision):
    try:
        return services.revisar_cambios(thread_id, revision.rechazados)
    except services.FlujoNoEspera as exc:
        raise HTTPException(409, str(exc))


@router.get("/archivos")
def descargar(ruta: str):
    """Descarga un DOCX generado. Solo dentro de salidas/: nada más del disco."""
    archivo = Path(ruta).resolve()
    if CARPETA_SALIDAS not in archivo.parents or archivo.suffix != ".docx" or not archivo.is_file():
        raise HTTPException(404, "Archivo no encontrado.")
    return FileResponse(archivo, filename=archivo.name)


# --------------------------------------------------------------
# Perfil, catálogo y análisis
# --------------------------------------------------------------

@router.get("/perfil")
def perfil():
    try:
        cv = services.cargar_cv_base()
        cv_resumen = {
            "nombre": cv.contacto.nombre,
            "perfil": cv.perfil,
            "experiencias": len(cv.experiencia),
            "proyectos": [{"nombre": p.nombre, "logros": p.logros, "stack": p.stack} for p in cv.proyectos],
            "habilidades": len(cv.skills_declaradas()),
        }
    except services.CVBaseNoEncontrado:
        cv_resumen = None
    return {
        "habilidades": services.listar_mi_perfil(),
        "cv": cv_resumen,
        "respuestas": [r.model_dump() for r in services.cargar_respuestas().values()],
    }


@router.get("/cv/base")
def leer_cv_base():
    """El CV base completo, para editarlo desde la app."""
    try:
        return services.cargar_cv_base().model_dump()
    except services.CVBaseNoEncontrado as e:
        raise HTTPException(404, str(e))


@router.put("/cv/base")
def escribir_cv_base(cv: CVBase):
    """Valida y guarda el CV base (data/cv_base.yaml), con respaldo de la versión anterior."""
    guardar_cv_base(cv)
    return {"ok": True, "habilidades": len(cv.skills_declaradas())}


class Habilidad(BaseModel):
    nombre: str = Field(min_length=1)
    categoria: str
    nivel: NIVELES
    meses_experiencia: Optional[int] = Field(default=None, ge=0)
    evidencia: str = Field(min_length=1)


@router.post("/perfil/habilidades")
def guardar_habilidad(h: Habilidad):
    services.guardar_habilidad(h.nombre.strip(), h.categoria, h.nivel, h.meses_experiencia, h.evidencia.strip())
    return {"ok": True}


@router.get("/catalogo/revision")
def catalogo_revision():
    return services.tecnologias_para_revisar()


@router.post("/catalogo/{technology_id}/aprobar")
def aprobar(technology_id: int):
    services.aprobar_tecnologia(technology_id)
    return {"ok": True}


@router.get("/analisis")
def analisis():
    return {"ofertas": len(services.listar_ofertas()), "demanda": services.demanda_tecnologias()}


# --------------------------------------------------------------
# Brújula
# --------------------------------------------------------------

@router.get("/brujula")
def brujula():
    return {**services.prioridades_estudio(), "plan": services.cargar_plan_estudio()}


@router.post("/brujula/plan")
def generar_plan():
    return services.generar_plan_estudio()


@router.post("/brujula/informe")
def informe():
    return {"ruta": services.generar_informe_brujula()}


# --------------------------------------------------------------
# Agentes en vivo (Server-Sent Events) y página Agentes
# --------------------------------------------------------------
# Cada línea "data: {...}" es un evento de un agente (empieza, termina,
# se pausa...) en el momento en que ocurre. El último es "resultado".

def _sse(eventos):
    import json

    for ev in eventos:
        yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"


def _transmision(eventos):
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        _sse(eventos), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/vivo/analizar")
def analizar_en_vivo(pedido: PedidoAnalisis):
    url = (pedido.url or "").strip() or None
    texto = (pedido.texto or "").strip() or None
    if not url and not texto:
        raise HTTPException(400, "Envía la URL o el texto de la oferta.")
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(400, "El link debe empezar con http:// o https://")
    return _transmision(services.analizar_oferta_en_vivo(url=url, text=texto))


@router.post("/vivo/cv/{job_id}/iniciar")
def iniciar_cv_en_vivo(job_id: int):
    try:
        services.cargar_cv_base()
    except services.CVBaseNoEncontrado as exc:
        raise HTTPException(400, str(exc))
    return _transmision(services.iniciar_adaptacion_cv_en_vivo(job_id))


@router.post("/vivo/cv/flujos/{thread_id}/responder")
def responder_en_vivo(thread_id: str, respuestas: list[Respuesta]):
    for r in respuestas:
        if r.la_tengo and not (r.donde or "").strip():
            raise HTTPException(400, f"Indica dónde usaste {r.tecnologia}, o marca que no lo tienes.")
    try:
        return _transmision(services.responder_preguntas_en_vivo(
            thread_id, [r.model_dump(exclude_none=True) for r in respuestas]))
    except services.FlujoNoEspera as exc:
        raise HTTPException(409, str(exc))


@router.post("/vivo/cv/flujos/{thread_id}/revisar")
def revisar_en_vivo(thread_id: str, revision: Revision):
    try:
        return _transmision(services.revisar_cambios_en_vivo(thread_id, revision.rechazados))
    except services.FlujoNoEspera as exc:
        raise HTTPException(409, str(exc))


@router.get("/agentes")
def agentes():
    from app import llm
    from app.agents import eventos

    catalogo = []
    for a in eventos.AGENTES:
        # La cadena completa: sus modelos de Gemini y luego el respaldo (Groq, Ollama).
        modelos = llm.cadena_para(a["modelo"]) if a.get("modelo") else []
        catalogo.append({**{k: v for k, v in a.items() if k != "modelo"}, "modelos": modelos})
    return {"agentes": catalogo, "actividad": eventos.actividad_reciente()}
