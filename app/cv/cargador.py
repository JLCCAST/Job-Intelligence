"""
cargador.py

Lee data/cv_base.yaml y lo devuelve validado como CVBase.
"""

from pathlib import Path

import yaml

from app.cv.modelo import CVBase

RAIZ = Path(__file__).resolve().parents[2]
RUTA_CV_BASE = RAIZ / "data" / "cv_base.yaml"


class CVBaseNoEncontrado(Exception):
    pass


def cargar_cv_base(ruta: Path = RUTA_CV_BASE) -> CVBase:
    if not ruta.exists():
        raise CVBaseNoEncontrado(
            f"No existe {ruta}. Copia data/cv_base.example.yaml como "
            "data/cv_base.yaml y complétalo con tu CV."
        )
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    return CVBase.model_validate(datos)
