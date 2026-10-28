"""
Tests del grafo de Batuta: que los agentes se llamen en orden y que
el flujo se corte donde corresponde. Todo lo que sale de la máquina
(red, Gemini, BD) se reemplaza con monkeypatch.
"""

from app.agents import archivero, balanza, batuta, lupa
from app.gemini import ExtractionResult
from app.repository import InsertJobResult
from app.schemas import JobExtraction
from app.scoring import MatchScoreResult


def _extraction(disponible=True):
    return JobExtraction(
        job_title="Analista BI",
        company_name="no_especificado",
        source_name="no_especificado",
        area="BI",
        english_level="no_especificado",
        is_offer_available=disponible,
        technologies=[],
    )


def _espiar(monkeypatch, disponible=True, duplicado=None):
    llamados = []

    def fake_extract(texto):
        llamados.append("lupa")
        return ExtractionResult(success=True, data=_extraction(disponible))

    def fake_insert(**kwargs):
        llamados.append("archivero")
        return InsertJobResult(
            job_id=7, company_id=1, source_id=1, tecnologias_vinculadas=0,
            tecnologias_creadas=[], tecnologias_para_revisar=[], tecnologias_duplicadas=[],
        )

    def fake_score(job_id):
        llamados.append("balanza")
        return MatchScoreResult(score=50.0, cumple_ingles=True, faltantes=[])

    monkeypatch.setattr(lupa, "extract_job_info", fake_extract)
    monkeypatch.setattr(lupa, "buscar_job_por_url", lambda url: duplicado)
    monkeypatch.setattr(archivero, "insert_job_with_technologies", fake_insert)
    monkeypatch.setattr(balanza, "calcular_y_guardar_match_score", fake_score)
    return llamados


def test_grafo_tiene_los_agentes_esperados():
    nodos = set(batuta.construir_grafo().get_graph().nodes)
    assert {"lupa_leer", "lupa_extraer", "archivero", "balanza"} <= nodos


def test_flujo_completo_llama_a_los_agentes_en_orden(monkeypatch):
    llamados = _espiar(monkeypatch)
    estado = batuta.analizar(text="Oferta de prueba " * 20)
    assert llamados == ["lupa", "archivero", "balanza"]
    assert estado["job_id"] == 7
    assert estado["match_score"] == 50.0


def test_oferta_cerrada_corta_antes_del_archivero(monkeypatch):
    llamados = _espiar(monkeypatch, disponible=False)
    estado = batuta.analizar(text="Oferta cerrada " * 20)
    assert llamados == ["lupa"]
    assert estado["registration_status"] == "offer_closed"


def test_duplicado_corta_antes_de_gemini(monkeypatch):
    llamados = _espiar(monkeypatch, duplicado=99)
    estado = batuta.analizar(url="https://ejemplo.com/oferta/1")
    assert llamados == []
    assert estado["job_id"] == 99
