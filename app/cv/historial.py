"""
historial.py

Registro de cada CV generado (data/historial_cv.json, privado). Cada
adaptación crea una versión nueva con fecha, sin borrar las
anteriores; al marcar una oferta como "Postulada" la última versión
queda como la ENVIADA. Así, si te llaman a entrevista, sabes
exactamente qué CV tiene la empresa.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.cv.cargador import RAIZ

RUTA_HISTORIAL = RAIZ / "data" / "historial_cv.json"


def _ruta(ruta: Optional[Path]) -> Path:
    return ruta or RUTA_HISTORIAL


def _cargar(ruta: Optional[Path] = None) -> list[dict]:
    ruta = _ruta(ruta)
    if not ruta.exists():
        return []
    return json.loads(ruta.read_text(encoding="utf-8"))


def _guardar(entradas: list[dict], ruta: Optional[Path] = None) -> None:
    ruta = _ruta(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(entradas, ensure_ascii=False, indent=1), encoding="utf-8")


def registrar(
    job_id: int,
    puesto: str,
    empresa: Optional[str],
    ruta_cv: str,
    ruta_brechas: str,
    usa_texto_de_pluma: bool,
    ruta: Optional[Path] = None,
) -> dict:
    entradas = _cargar(ruta)
    entrada = {
        "job_id": job_id,
        "version": 1 + sum(1 for e in entradas if e["job_id"] == job_id),
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "puesto": puesto,
        "empresa": empresa,
        "ruta_cv": ruta_cv,
        "ruta_brechas": ruta_brechas,
        "usa_texto_de_pluma": usa_texto_de_pluma,
        "enviado": False,
        "fecha_envio": None,
    }
    entradas.append(entrada)
    _guardar(entradas, ruta)
    return entrada


def versiones(job_id: int, ruta: Optional[Path] = None) -> list[dict]:
    """Versiones del CV para una oferta, de la más nueva a la más antigua."""
    return sorted((e for e in _cargar(ruta) if e["job_id"] == job_id), key=lambda e: -e["version"])


def marcar_enviado(job_id: int, ruta: Optional[Path] = None) -> Optional[dict]:
    """
    Marca la última versión como la enviada. Si ya había una enviada,
    no la cambia: lo que la empresa recibió no se reescribe.
    """
    entradas = _cargar(ruta)
    de_la_oferta = [e for e in entradas if e["job_id"] == job_id]
    if not de_la_oferta:
        return None
    ya_enviada = next((e for e in de_la_oferta if e["enviado"]), None)
    if ya_enviada:
        return ya_enviada
    ultima = max(de_la_oferta, key=lambda e: e["version"])
    ultima["enviado"] = True
    ultima["fecha_envio"] = datetime.now().isoformat(timespec="seconds")
    _guardar(entradas, ruta)
    return ultima
