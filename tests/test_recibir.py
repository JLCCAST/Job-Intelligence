"""Tests del marcador: la API recibe la oferta y la app la toma una sola vez."""

from fastapi.testclient import TestClient

from app import pendientes
from app.main import app

client = TestClient(app)


def test_recibir_guarda_la_oferta_y_redirige_a_analizar(monkeypatch, tmp_path):
    monkeypatch.setattr(pendientes, "CARPETA_PENDIENTES", tmp_path)
    r = client.post(
        "/recibir",
        data={"url": "https://pe.computrabajo.com/ofertas/123", "texto": "Analista BI · SQL y Power BI"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    destino = r.headers["location"]
    assert destino.startswith("http://localhost:8501/analizar?pendiente=")

    id_ = destino.split("=")[-1]
    oferta = pendientes.tomar(id_)
    assert oferta["texto"] == "Analista BI · SQL y Power BI"
    assert oferta["url"] == "https://pe.computrabajo.com/ofertas/123"
    assert pendientes.tomar(id_) is None          # se borra al tomarla


def test_recibir_sin_texto_da_error(monkeypatch, tmp_path):
    monkeypatch.setattr(pendientes, "CARPETA_PENDIENTES", tmp_path)
    assert client.post("/recibir", data={"url": "https://x.com", "texto": "  "}).status_code == 400


def test_tomar_rechaza_ids_raros(tmp_path):
    assert pendientes.tomar("../../.env", carpeta=tmp_path) is None
