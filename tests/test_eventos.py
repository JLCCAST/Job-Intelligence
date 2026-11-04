"""Tests de los eventos en vivo de los agentes y su transmisión por la API."""

import json

from fastapi.testclient import TestClient

from app import services
from app.agents import batuta, eventos, lupa
from app.main import app
from tests.test_batuta import _espiar


def test_analizar_en_vivo_muestra_lupa_archivero_y_balanza(monkeypatch, tmp_path):
    monkeypatch.setattr(eventos, "RUTA_ACTIVIDAD", tmp_path / "a.jsonl")
    _espiar(monkeypatch)
    evs = list(services.analizar_oferta_en_vivo(text="Oferta de prueba " * 20))

    pasos = [(e["agente"], e["estado"]) for e in evs if e["tipo"] == "fin"]
    assert pasos == [("lupa", "ok"), ("lupa", "ok"), ("archivero", "ok"), ("balanza", "ok"), ("batuta", "ok")]
    assert evs[0] == {"tipo": "inicio", "nodo": "batuta", "agente": "batuta", "accion": "Organizando el análisis de la oferta"}
    assert "Match Score: 50.0%" in [e for e in evs if e.get("agente") == "balanza" and e["tipo"] == "fin"][0]["resumen"]
    assert evs[-1]["tipo"] == "resultado" and evs[-1]["datos"]["job_id"] == 7


def test_oferta_duplicada_se_ve_como_detenida(monkeypatch, tmp_path):
    monkeypatch.setattr(eventos, "RUTA_ACTIVIDAD", tmp_path / "a.jsonl")
    _espiar(monkeypatch, duplicado=99)
    evs = list(batuta.analizar_en_vivo(url="https://ejemplo.com/1"))
    fin = [e for e in evs if e["tipo"] == "fin"]
    assert len(fin) == 1 and fin[0]["estado"] == "detenido" and "job_id 99" in fin[0]["resumen"]


def test_un_error_en_un_agente_llega_como_evento(monkeypatch, tmp_path):
    monkeypatch.setattr(eventos, "RUTA_ACTIVIDAD", tmp_path / "a.jsonl")
    _espiar(monkeypatch)
    monkeypatch.setattr(lupa, "extract_job_info", lambda t: (_ for _ in ()).throw(RuntimeError("se cayó")))
    evs = list(services.analizar_oferta_en_vivo(text="Oferta " * 40))
    assert evs[-1]["tipo"] == "error" and "se cayó" in evs[-1]["mensaje"]


def test_endpoint_transmite_eventos_sse(monkeypatch):
    def falso(url=None, text=None):
        yield {"tipo": "inicio", "agente": "lupa"}
        yield {"tipo": "resultado", "datos": {"ok": True}}

    monkeypatch.setattr(services, "analizar_oferta_en_vivo", falso)
    r = TestClient(app).post("/api/vivo/analizar", json={"texto": "hola"})
    assert r.headers["content-type"].startswith("text/event-stream")
    datos = [json.loads(l[6:]) for l in r.text.split("\n") if l.startswith("data: ")]
    assert datos == [{"tipo": "inicio", "agente": "lupa"}, {"tipo": "resultado", "datos": {"ok": True}}]


def test_registro_de_actividad_guarda_lo_ultimo_primero(tmp_path):
    ruta = tmp_path / "a.jsonl"
    eventos.registrar("sabueso", "Revisé 10 ofertas", ruta=ruta)
    eventos.registrar("lupa", "Leí la oferta", ruta=ruta)
    assert [a["agente"] for a in eventos.actividad_reciente(ruta=ruta)] == ["lupa", "sabueso"]


def test_catalogo_de_agentes_incluye_modelos(monkeypatch, tmp_path):
    monkeypatch.setattr(eventos, "RUTA_ACTIVIDAD", tmp_path / "a.jsonl")
    datos = TestClient(app).get("/api/agentes").json()
    por_id = {a["id"]: a for a in datos["agentes"]}
    assert len(por_id) == 11 and por_id["lupa"]["gemini"] and por_id["lupa"]["modelos"]
    assert por_id["balanza"]["modelos"] == []
