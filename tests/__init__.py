"""
Usamos monkeypatch para reemplazar fetch_html por una versión falsa
que no hace red real 
"""

from fastapi.testclient import TestClient

from app.main import app
from app.scraper import FetchResult
import app.main as main_module

client = TestClient(app)


def test_analyze_job_con_texto_manual():
    response = client.post(
        "/analyze-job",
        json={"text": "Buscamos Analista de Datos con SQL y Power BI."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "manual_text"
    assert data["extraction_status"] == "success"
    assert "Analista de Datos" in data["cleaned_text"]


def test_analyze_job_sin_url_ni_text_falla_validacion():

    response = client.post("/analyze-job", json={})

    assert response.status_code == 422


def test_analyze_job_con_url_scraping_exitoso(monkeypatch):
    html_falso = "<html><body><main>" \
                 "<h1>Practicante BI</h1>" \
                 "<p>" + ("Requisitos de la oferta laboral de prueba. " * 10) + "</p>" \
                 "</main></body></html>"

    def fake_fetch_html(url: str) -> FetchResult:
        return FetchResult(success=True, html=html_falso, status_code=200)

    monkeypatch.setattr(main_module, "fetch_html", fake_fetch_html)

    response = client.post(
        "/analyze-job",
        json={"url": "https://empresa-de-prueba.com/oferta"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "url"
    assert data["extraction_status"] == "success"
    assert "Practicante BI" in data["cleaned_text"]


def test_analyze_job_con_url_scraping_fallido(monkeypatch):
    def fake_fetch_html_fallido(url: str) -> FetchResult:
        return FetchResult(success=False, error="Timeout: el servidor no respondió en 10s.")

    monkeypatch.setattr(main_module, "fetch_html", fake_fetch_html_fallido)

    response = client.post(
        "/analyze-job",
        json={"url": "https://sitio-caido-de-prueba.com/oferta"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["extraction_status"] == "failed"
    assert "Timeout" in data["error_detail"]