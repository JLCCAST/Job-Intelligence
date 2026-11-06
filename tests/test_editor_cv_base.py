"""
Tests del editor del CV base: guardar desde la app tiene que dejar un
YAML que se vuelve a cargar igual, con respaldo de la versión anterior,
y rechazar un CV inválido sin tocar el archivo.
"""

import shutil

import pytest
from fastapi.testclient import TestClient

from app.cv import cargador
from app.cv.cargador import RAIZ, cargar_cv_base, guardar_cv_base
from app.main import app

EJEMPLO = RAIZ / "data" / "cv_base.example.yaml"


@pytest.fixture
def ruta(tmp_path, monkeypatch):
    """Un CV base temporal en lugar de data/cv_base.yaml."""
    destino = tmp_path / "cv_base.yaml"
    shutil.copy(EJEMPLO, destino)
    monkeypatch.setattr(cargador, "RUTA_CV_BASE", destino)
    return destino


def test_guardar_y_cargar_da_el_mismo_cv(ruta):
    cv = cargar_cv_base()
    cv.proyectos[0].logros.append("Documenté el modelo de datos con un diccionario de 20 campos.")
    guardar_cv_base(cv)
    assert cargar_cv_base() == cv
    assert ruta.read_text(encoding="utf-8").startswith("# CV base -- PRIVADO")


def test_guardar_deja_respaldo_de_la_version_anterior(ruta):
    antes = ruta.read_text(encoding="utf-8")
    cv = cargar_cv_base()
    cv.perfil = "Perfil nuevo."
    guardar_cv_base(cv)
    respaldo = ruta.with_name("cv_base.respaldo.yaml")
    assert respaldo.read_text(encoding="utf-8") == antes
    assert not ruta.with_name("cv_base.tmp.yaml").exists()


def test_api_lee_y_guarda_el_cv_base(ruta):
    client = TestClient(app)
    datos = client.get("/api/cv/base").json()
    datos["proyectos"].append({
        "nombre": "Dashboard de RR. HH.", "contexto": "Curso", "logros": ["Construí un dashboard en Power BI."],
        "stack": ["Power BI", "DAX"],
    })
    r = client.put("/api/cv/base", json=datos)
    assert r.status_code == 200
    cv = cargar_cv_base()
    assert cv.proyectos[-1].nombre == "Dashboard de RR. HH."
    assert "dax" in cv.skills_declaradas()


def test_api_rechaza_un_proyecto_sin_logros_y_no_toca_el_archivo(ruta):
    client = TestClient(app)
    antes = ruta.read_text(encoding="utf-8")
    datos = client.get("/api/cv/base").json()
    datos["proyectos"].append({"nombre": "Vacío", "logros": [], "stack": []})
    assert client.put("/api/cv/base", json=datos).status_code == 422
    assert ruta.read_text(encoding="utf-8") == antes
