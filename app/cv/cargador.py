"""
cargador.py

Lee data/cv_base.yaml y lo devuelve validado como CVBase.
"""

from pathlib import Path
from typing import Optional

import yaml

from app.cv.modelo import CVBase

RAIZ = Path(__file__).resolve().parents[2]
RUTA_CV_BASE = RAIZ / "data" / "cv_base.yaml"


class CVBaseNoEncontrado(Exception):
    pass


def cargar_cv_base(ruta: Optional[Path] = None) -> CVBase:
    ruta = ruta or RUTA_CV_BASE
    if not ruta.exists():
        raise CVBaseNoEncontrado(
            f"No existe {ruta}. Copia data/cv_base.example.yaml como "
            "data/cv_base.yaml y complétalo con tu CV."
        )
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    return CVBase.model_validate(datos)


ENCABEZADO = """\
# CV base -- PRIVADO (está en .gitignore, no se sube al repo).
# Es la única fuente de verdad para Pluma: solo puede usar lo que está aquí.
# Lo puedes editar en la app (Mi perfil > CV base) o a mano en este archivo.
# Al guardar desde la app, la versión anterior queda en cv_base.respaldo.yaml.
#
# Reglas: cada logro empieza con un verbo en pasado y, si se puede, termina
# con una cifra real; si solo apoyaste, dilo ("Participé en..."). Una
# tecnología que no esté en un `stack` ni en `habilidades`, Pluma no la usa.

"""


def guardar_cv_base(cv: CVBase, ruta: Optional[Path] = None) -> None:
    """
    Escribe el CV base. Antes guarda la versión anterior como respaldo
    (una sola, la última), por si un cambio sale mal.
    """
    ruta = ruta or RUTA_CV_BASE
    if ruta.exists():
        respaldo = ruta.with_name(ruta.stem + ".respaldo" + ruta.suffix)
        respaldo.write_bytes(ruta.read_bytes())
    datos = cv.model_dump(exclude_none=True)
    for clave in [c for c, v in datos.items() if v == []]:
        del datos[clave]  # secciones vacías: fuera, el YAML queda más limpio
    texto = yaml.safe_dump(datos, allow_unicode=True, sort_keys=False, width=1000)
    temporal = ruta.with_name(ruta.stem + ".tmp" + ruta.suffix)
    temporal.write_text(ENCABEZADO + texto, encoding="utf-8")
    temporal.replace(ruta)  # todo o nada: no queda un archivo a medias
