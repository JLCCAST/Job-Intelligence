"""
pendientes.py

Ofertas enviadas desde el navegador con el marcador "Enviar a
Job-Intelligence", esperando a que las revises en "Analizar oferta".
Se guardan en data/pendientes/ (privado) y se borran al abrirlas.

No se analizan solas: llegan como texto prellenado y tú decides si
analizar. Así una página cualquiera no puede gastar tu cuota de Gemini
ni registrar ofertas sin que lo veas.
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.cv.cargador import RAIZ

CARPETA_PENDIENTES = RAIZ / "data" / "pendientes"
MAX_CARACTERES = 60_000
_ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")


def _carpeta(carpeta: Optional[Path]) -> Path:
    return carpeta or CARPETA_PENDIENTES


def guardar(url: str, texto: str, carpeta: Optional[Path] = None) -> str:
    carpeta = _carpeta(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    id_ = uuid.uuid4().hex
    datos = {
        "url": (url or "").strip()[:2000],
        "texto": (texto or "").strip()[:MAX_CARACTERES],
        "recibido": datetime.now().isoformat(timespec="seconds"),
    }
    (carpeta / f"{id_}.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return id_


def tomar(id_: str, carpeta: Optional[Path] = None) -> Optional[dict]:
    """Devuelve la oferta pendiente y la borra. None si no existe o el id no es válido."""
    if not _ID_VALIDO.match(id_ or ""):
        return None
    ruta = _carpeta(carpeta) / f"{id_}.json"
    if not ruta.exists():
        return None
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    ruta.unlink()
    return datos
