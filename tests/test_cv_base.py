"""
Tests del CV base. Usan la plantilla pública (cv_base.example.yaml)
para no depender del CV real, que no está en el repo.
"""

import pytest
from pydantic import ValidationError

from app.cv.cargador import RAIZ, CVBaseNoEncontrado, cargar_cv_base

EJEMPLO = RAIZ / "data" / "cv_base.example.yaml"


def test_la_plantilla_es_valida():
    cv = cargar_cv_base(EJEMPLO)
    assert cv.contacto.nombre
    assert cv.proyectos and cv.proyectos[0].logros


def test_skills_declaradas_junta_habilidades_y_stacks_en_minusculas():
    cv = cargar_cv_base(EJEMPLO)
    skills = cv.skills_declaradas()
    assert "sql" in skills           # de habilidades
    assert "sql server" in skills    # del stack de un proyecto
    assert "excel" in skills         # del stack de una experiencia
    assert "airflow" not in skills


def test_archivo_inexistente_da_mensaje_claro(tmp_path):
    with pytest.raises(CVBaseNoEncontrado, match="cv_base.example.yaml"):
        cargar_cv_base(tmp_path / "no_existe.yaml")


def test_proyecto_sin_logros_no_valida(tmp_path):
    ruta = tmp_path / "cv.yaml"
    ruta.write_text(
        "contacto: {nombre: X, email: x@x.com}\n"
        "perfil: algo\n"
        "proyectos:\n  - nombre: Vacío\n    logros: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        cargar_cv_base(ruta)


def test_skills_con_formato_conserva_mayusculas_sin_duplicar():
    cv = cargar_cv_base(EJEMPLO)
    formato = cv.skills_con_formato()
    assert "Power BI" in formato and "power bi" not in formato
    assert len(formato) == len(cv.skills_declaradas())
