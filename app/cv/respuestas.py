"""
respuestas.py

Lo que le respondiste al Preguntón, guardado en data/respuestas.yaml
(privado, en .gitignore). Se reutiliza entre ofertas: si ya dijiste
que no sabes Airflow, no te lo vuelve a preguntar en la siguiente.

Para Pluma, una respuesta con `la_tengo=True` cuenta igual que una
habilidad del CV base: es información que TÚ confirmaste.
"""

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel

from app.cv.cargador import RAIZ

RUTA_RESPUESTAS = RAIZ / "data" / "respuestas.yaml"


class Respuesta(BaseModel):
    tecnologia: str
    la_tengo: bool
    nivel: Optional[Literal["basico", "intermedio", "avanzado"]] = None
    donde: Optional[str] = None    # proyecto, trabajo o curso donde lo usaste
    detalle: Optional[str] = None  # qué hiciste con eso, en tus palabras


def _clave(tecnologia: str) -> str:
    return tecnologia.strip().lower()


def cargar_respuestas(ruta: Optional[Path] = None) -> dict[str, Respuesta]:
    """{nombre en minúsculas: Respuesta}. Vacío si aún no hay archivo."""
    ruta = ruta or RUTA_RESPUESTAS
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or []
    respuestas = [Respuesta.model_validate(d) for d in datos]
    return {_clave(r.tecnologia): r for r in respuestas}


def guardar_respuestas(nuevas: list[Respuesta], ruta: Optional[Path] = None) -> None:
    """Agrega o reemplaza respuestas (la última respuesta manda)."""
    ruta = ruta or RUTA_RESPUESTAS
    todas = cargar_respuestas(ruta)
    for r in nuevas:
        todas[_clave(r.tecnologia)] = r

    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            [r.model_dump(exclude_none=True) for r in todas.values()],
            f, allow_unicode=True, sort_keys=False,
        )
