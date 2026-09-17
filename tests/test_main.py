"""
Tests del endpoint /analyze-job.

El endpoint ahora encadena scraper -> cleaner -> Gemini -> BD, así
que se reemplazan con monkeypatch las tres piezas que salen de la
máquina: fetch_html (red), extract_job_info (API de Gemini) y las
funciones de repository (Supabase). Así los tests corren sin red,
sin cuota y sin escribir en la base.
"""

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.repository import InsertJobResult
from app.scoring import MatchScoreResult
from app.scraper import FetchResult
from app.schemas import ExtractedTechnology, JobExtraction
from app.gemini import ExtractionResult

client = TestClient(app)

TEXTO_LARGO = "Requisitos de la oferta laboral de prueba. " * 10


def _extraction(disponible=True, source_name="no_especificado", techs=None):
    if techs is None:
        techs = [
            ExtractedTechnology(
                name="Python",
                category="Programming",
                requirement_type="required",
                level="avanzado",
                confidence=1.0,
                evidence_text="conocimientos avanzados de Python",
            )
        ]
    return JobExtraction(
        job_title="Analista de Datos",
        company_name="Banco Pichincha",
        source_name=source_name,
        area="Data_Analytics",
        english_level="intermedio",
        is_offer_available=disponible,
        technologies=techs if disponible else [],
    )


@pytest.fixture
def espia(monkeypatch):
    """
    Reemplaza Gemini y la BD, y registra lo que se llamó, para poder
    afirmar cosas como "NO se debió llamar a Gemini".
    """
    registro = {"gemini": 0, "insert": 0, "source_name": None, "duplicado": None}

    def fake_extract(texto):
        registro["gemini"] += 1
        return ExtractionResult(success=True, data=registro["extraction"])

    def fake_insert(extraction, source_name, url=None, descripcion_raw=None,
                    descripcion_limpia=None, status_nombre="Registrada"):
        registro["insert"] += 1
        registro["source_name"] = source_name
        return InsertJobResult(
            job_id=123, company_id=1, source_id=5,
            tecnologias_vinculadas=len(extraction.technologies),
            tecnologias_creadas=["Python"],
            tecnologias_para_revisar=[],
            tecnologias_duplicadas=[],
        )

    def fake_buscar(url):
        return registro["duplicado"]

    def fake_score(job_id):
        registro["score"] = job_id
        return MatchScoreResult(score=87.5, cumple_ingles=True, faltantes=["Azure"])

    registro["extraction"] = _extraction()
    monkeypatch.setattr(main_module, "calcular_y_guardar_match_score", fake_score)
    monkeypatch.setattr(main_module, "extract_job_info", fake_extract)
    monkeypatch.setattr(main_module, "insert_job_with_technologies", fake_insert)
    monkeypatch.setattr(main_module, "buscar_job_por_url", fake_buscar)
    return registro


def _mock_fetch_ok(monkeypatch, html=None):
    if html is None:
        html = f"<html><body><main><h1>Practicante BI</h1><p>{TEXTO_LARGO}</p></main></body></html>"
    monkeypatch.setattr(
        main_module, "fetch_html",
        lambda url: FetchResult(success=True, html=html, status_code=200),
    )


# --------- Validación de entrada ---------

def test_sin_url_ni_text_falla_validacion():
    assert client.post("/analyze-job", json={}).status_code == 422


# --------- Camino feliz ---------

def test_texto_manual_se_guarda(espia):
    r = client.post("/analyze-job", json={"text": TEXTO_LARGO})
    assert r.status_code == 200
    d = r.json()

    assert d["source"] == "manual_text"
    assert d["extraction_status"] == "success"
    assert d["registration_status"] == "saved"
    assert d["job_id"] == 123
    assert d["tecnologias_vinculadas"] == 1
    assert d["match_score"] == 87.5
    assert d["cumple_ingles"] is True
    assert d["tecnologias_faltantes"] == ["Azure"]


def test_url_scraping_exitoso_se_guarda(espia, monkeypatch):
    _mock_fetch_ok(monkeypatch)

    r = client.post("/analyze-job", json={"url": "https://empresa-de-prueba.com/oferta"})
    d = r.json()

    assert d["source"] == "url"
    assert d["registration_status"] == "saved"
    assert "Practicante BI" in d["cleaned_text"]


# --------- Fuente: el dominio manda sobre Gemini ---------

def test_con_url_gana_el_dominio_sobre_gemini(espia, monkeypatch):
    _mock_fetch_ok(monkeypatch)
    espia["extraction"] = _extraction(source_name="Bumeran")  # Gemini dice Bumeran

    client.post("/analyze-job", json={"url": "https://www.linkedin.com/jobs/view/1"})

    assert espia["source_name"] == "LinkedIn"


def test_sin_url_se_usa_la_fuente_de_gemini(espia):
    espia["extraction"] = _extraction(source_name="Computrabajo")

    client.post("/analyze-job", json={"text": TEXTO_LARGO})

    assert espia["source_name"] == "Computrabajo"


# --------- Caminos que NO deben guardar ---------

def test_scraping_fallido_no_llama_a_gemini(espia, monkeypatch):
    monkeypatch.setattr(
        main_module, "fetch_html",
        lambda url: FetchResult(success=False, error="Timeout: el servidor no respondió en 10s."),
    )

    d = client.post("/analyze-job", json={"url": "https://sitio-caido.com/oferta"}).json()

    assert d["extraction_status"] == "failed"
    assert d["registration_status"] == "not_attempted"
    assert "Timeout" in d["error_detail"]
    assert espia["gemini"] == 0   # no se gastó cuota de la API
    assert espia["insert"] == 0


def test_gemini_caido_no_guarda_nada(espia, monkeypatch):
    _mock_fetch_ok(monkeypatch)
    monkeypatch.setattr(
        main_module, "extract_job_info",
        lambda texto: ExtractionResult(success=False, error="503 UNAVAILABLE"),
    )

    d = client.post("/analyze-job", json={"url": "https://empresa.com/oferta"}).json()

    assert d["extraction_status"] == "failed"
    assert d["registration_status"] == "not_attempted"
    assert "503" in d["error_detail"]
    assert espia["insert"] == 0


def test_oferta_cerrada_no_se_guarda(espia):
    espia["extraction"] = _extraction(disponible=False)

    d = client.post("/analyze-job", json={"text": TEXTO_LARGO}).json()

    assert d["registration_status"] == "offer_closed"
    assert d["job_id"] is None
    assert espia["insert"] == 0
    # La extracción sí se devuelve, para poder ver qué detectó.
    assert d["extraction"]["is_offer_available"] is False


def test_url_duplicada_devuelve_job_existente_sin_llamar_a_gemini(espia, monkeypatch):
    espia["duplicado"] = 77
    _mock_fetch_ok(monkeypatch)

    d = client.post("/analyze-job", json={"url": "https://empresa.com/oferta-repetida"}).json()

    assert d["registration_status"] == "duplicate"
    assert d["job_id"] == 77
    assert espia["gemini"] == 0   # clave: no se gasta cuota en un duplicado
    assert espia["insert"] == 0


# --------- Texto corto -> partial ---------

def test_texto_corto_queda_partial(espia):
    d = client.post("/analyze-job", json={"text": "Buscamos Analista con SQL."}).json()

    assert d["extraction_status"] == "partial"
    assert d["registration_status"] == "saved"   # partial no impide guardar
