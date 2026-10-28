"""Tests del historial de CVs enviados."""

from app import services
from app.cv import historial


def test_marcar_enviado_toma_la_ultima_version_y_no_la_cambia_despues(tmp_path):
    ruta = tmp_path / "h.json"
    historial.registrar(7, "Analista", "X", "v1.docx", "b1.docx", True, ruta=ruta)
    historial.registrar(7, "Analista", "X", "v2.docx", "b2.docx", True, ruta=ruta)

    enviado = historial.marcar_enviado(7, ruta=ruta)
    assert enviado["ruta_cv"] == "v2.docx" and enviado["fecha_envio"]

    # Una versión nueva después de postular no reemplaza a la enviada.
    historial.registrar(7, "Analista", "X", "v3.docx", "b3.docx", True, ruta=ruta)
    assert historial.marcar_enviado(7, ruta=ruta)["ruta_cv"] == "v2.docx"
    assert [v["enviado"] for v in historial.versiones(7, ruta=ruta)] == [False, True, False]


def test_sin_cv_generado_no_hay_nada_que_marcar(tmp_path):
    assert historial.marcar_enviado(99, ruta=tmp_path / "h.json") is None


def test_postular_marca_el_cv_enviado(monkeypatch, tmp_path):
    from app import consultas

    monkeypatch.setattr(historial, "RUTA_HISTORIAL", tmp_path / "h.json")
    monkeypatch.setattr(consultas, "cambiar_estado", lambda *a: None)
    historial.registrar(5, "BI", "Y", "cv.docx", "br.docx", True)

    services.cambiar_estado(5, "Entrevista")
    assert not historial.versiones(5)[0]["enviado"]
    services.cambiar_estado(5, "Postulada")
    assert historial.versiones(5)[0]["enviado"]
