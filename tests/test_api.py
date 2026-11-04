"""
Tests de la API REST (/api) que usa el frontend React. Los servicios
se reemplazan: sin Supabase, sin Gemini, sin archivos reales.
"""

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app import api, services
from app.main import app

client = TestClient(app)

OFERTA = {"job_id": 2, "puesto": "Practicante BI", "empresa": "Alicorp", "fuente": "Otro",
          "estado": "Registrada", "match_score": 92.5, "area": "BI",
          "fecha_registro": "2026-10-01T10:00:00", "url": None}
ESTADOS = ["Registrada", "Analizada", "Postulada", "Entrevista", "Oferta", "Rechazada", "Descartada"]


@pytest.fixture(autouse=True)
def servicios(monkeypatch):
    llamadas = {}
    monkeypatch.setattr(services, "listar_ofertas", lambda: [OFERTA])
    monkeypatch.setattr(services, "listar_estados", lambda: ESTADOS)
    monkeypatch.setattr(services, "cambiar_estado", lambda *a: llamadas.update(estado=a))
    monkeypatch.setattr(services, "guardar_habilidad", lambda *a: llamadas.update(habilidad=a))
    return llamadas


def test_listar_ofertas():
    assert client.get("/api/ofertas").json() == [OFERTA]


def test_cambiar_estado_valida_el_estado(servicios):
    assert client.post("/api/ofertas/2/estado", json={"estado": "Postulada", "nota": " Envié el CV "}).json() == {"ok": True}
    assert servicios["estado"] == (2, "Postulada", "Envié el CV")
    assert client.post("/api/ofertas/2/estado", json={"estado": "Inventado"}).status_code == 400


def test_analizar_valida_la_entrada():
    assert client.post("/api/analizar", json={}).status_code == 400
    assert client.post("/api/analizar", json={"texto": "x", "url": "linkedin.com/1"}).status_code == 400


def test_responder_exige_donde_si_la_tiene(monkeypatch):
    monkeypatch.setattr(services, "responder_preguntas", lambda t, r: {"thread_id": t, "respuestas": r})
    malo = client.post("/api/cv/flujos/t1/responder", json=[{"tecnologia": "dbt", "la_tengo": True}])
    assert malo.status_code == 400
    bueno = client.post("/api/cv/flujos/t1/responder", json=[{"tecnologia": "dbt", "la_tengo": False}])
    assert bueno.json()["respuestas"] == [{"tecnologia": "dbt", "la_tengo": False}]


def test_guardar_habilidad_exige_evidencia(servicios):
    datos = {"nombre": "dbt", "categoria": "Framework", "nivel": "basico", "evidencia": ""}
    assert client.post("/api/perfil/habilidades", json=datos).status_code == 422
    datos["evidencia"] = "Curso con laboratorio"
    assert client.post("/api/perfil/habilidades", json=datos).status_code == 200
    assert servicios["habilidad"] == ("dbt", "Framework", "basico", None, "Curso con laboratorio")


def test_descargar_solo_permite_docx_dentro_de_salidas(monkeypatch, tmp_path):
    salidas = tmp_path / "salidas"
    (salidas / "cv").mkdir(parents=True)
    cv = salidas / "cv" / "CV.docx"
    cv.write_bytes(b"docx")
    (tmp_path / "secreto.docx").write_bytes(b"no")
    monkeypatch.setattr(api, "CARPETA_SALIDAS", salidas.resolve())

    assert client.get("/api/archivos", params={"ruta": str(cv)}).content == b"docx"
    assert client.get("/api/archivos", params={"ruta": str(tmp_path / "secreto.docx")}).status_code == 404
    assert client.get("/api/archivos", params={"ruta": str(salidas / "cv" / ".." / ".." / "secreto.docx")}).status_code == 404


def test_supabase_caido_da_503_con_mensaje(monkeypatch):
    def caido():
        raise psycopg2.OperationalError("tenant not found")

    monkeypatch.setattr(services, "listar_ofertas", caido)
    r = TestClient(app, raise_server_exceptions=False).get("/api/ofertas")
    assert r.status_code == 503
    assert "Supabase" in r.json()["detail"]
