"""
Tests de la app de Streamlit con AppTest: se ejecutan las páginas
sin navegador, con los servicios reemplazados (sin Supabase ni
Gemini), para comprobar que se renderizan y llaman a lo correcto.
"""

import psycopg2
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app import services
from app.cv.cargador import RAIZ, cargar_cv_base


def _pagina(nombre: str) -> AppTest:
    """
    Carga la app completa (con su navegación) y va a la página pedida,
    como en el uso real: así funcionan los enlaces entre páginas.
    """
    at = AppTest.from_file(str(RAIZ / "streamlit_app.py"), default_timeout=30)
    at.run()
    if nombre != "inicio.py":
        at.switch_page(f"ui/{nombre}")
    return at


OFERTAS = [
    {"job_id": 2, "puesto": "Practicante BI", "empresa": "Alicorp", "fuente": "LinkedIn",
     "estado": "Registrada", "match_score": 92.5, "area": "BI",
     "fecha_registro": "2026-10-01T10:00:00", "url": None},
]
ESTADOS = ["Registrada", "Analizada", "Postulada", "Entrevista", "Oferta", "Rechazada", "Descartada"]


@pytest.fixture(autouse=True)
def base(monkeypatch):
    """
    Lo mínimo para que cargue Inicio (la página por defecto) sin
    Supabase. Cada test reemplaza encima lo que necesita.
    """
    st.cache_data.clear()  # la app guarda lecturas en caché; cada test parte limpio
    ejemplo = cargar_cv_base(RAIZ / "data" / "cv_base.example.yaml")
    monkeypatch.setattr(services, "listar_ofertas", lambda: OFERTAS)
    monkeypatch.setattr(services, "listar_estados", lambda: ESTADOS)
    monkeypatch.setattr(services, "historial_estados", lambda job_id: [])
    monkeypatch.setattr(services, "tecnologias_para_revisar", lambda: [])
    monkeypatch.setattr(services, "resumen_centinela", lambda: {"nuevas": [], "recordatorios": []})
    monkeypatch.setattr(services, "cargar_cv_base", lambda: ejemplo)
    monkeypatch.setattr(services, "versiones_cv", lambda job_id: [])


@pytest.fixture
def servicios_falsos(monkeypatch):
    llamadas = {}
    monkeypatch.setattr(
        services, "cambiar_estado",
        lambda job_id, estado, nota: llamadas.update(estado=(job_id, estado, nota)),
    )
    return llamadas


def test_inicio_muestra_metricas(servicios_falsos):
    at = _pagina("inicio.py").run()
    assert not at.exception
    assert at.metric[0].value == "1"
    assert at.metric[1].value == "1"          # en la bandeja (estado Registrada)
    assert at.metric[3].value == "92.5%"


def test_postulaciones_cambia_estado(servicios_falsos):
    at = _pagina("postulaciones.py").run()
    assert not at.exception
    at.selectbox[1].set_value("Postulada")
    at.text_input[0].set_value("Envié el CV adaptado")
    at.button[0].click().run()
    assert servicios_falsos["estado"] == (2, "Postulada", "Envié el CV adaptado")


def test_sin_supabase_muestra_mensaje_claro(monkeypatch):
    def caido():
        raise psycopg2.OperationalError("tenant not found")

    monkeypatch.setattr(services, "listar_ofertas", caido)
    monkeypatch.setattr(services, "tecnologias_para_revisar", lambda: [])
    at = _pagina("inicio.py").run()
    assert "No pude conectar con Supabase" in at.error[0].value


def test_adaptar_cv_muestra_preguntas_y_envia_respuestas(servicios_falsos, monkeypatch, tmp_path):
    cv, brechas = tmp_path / "CV.docx", tmp_path / "Brechas.docx"
    cv.write_bytes(b"x")
    brechas.write_bytes(b"y")
    recibidas = {}
    # El CV real no está en el repo: se usa la plantilla pública.
    ejemplo = cargar_cv_base(RAIZ / "data" / "cv_base.example.yaml")
    monkeypatch.setattr(services, "cargar_cv_base", lambda: ejemplo)

    monkeypatch.setattr(services, "iniciar_adaptacion_cv", lambda job_id: {
        "thread_id": "t1", "esperando_respuestas": True,
        "preguntas": [{"tecnologia": "Airflow", "requirement_type": "required", "texto": "¿Usaste Airflow?"}],
        "ruta_cv": None, "ruta_brechas": None, "usa_texto_de_pluma": False, "avisos": [],
    })

    def fake_responder(thread_id, respuestas):
        recibidas["respuestas"] = respuestas
        return {"thread_id": thread_id, "esperando_respuestas": False, "preguntas": [],
                "ruta_cv": str(cv), "ruta_brechas": str(brechas), "usa_texto_de_pluma": True, "avisos": []}

    monkeypatch.setattr(services, "responder_preguntas", fake_responder)

    at = _pagina("adaptar_cv.py").run()
    at.button[0].click().run()                       # "Adaptar CV"
    assert any("Airflow" in m.value for m in at.markdown)

    at.button[-1].click().run()                      # enviar con "No" por defecto
    assert not at.exception
    assert recibidas["respuestas"] == [{"tecnologia": "Airflow", "la_tengo": False}]
    assert "Tu CV está listo" in at.success[0].value


def test_bandeja_muestra_registradas_y_descarta(servicios_falsos):
    at = _pagina("bandeja.py").run()
    assert not at.exception
    at.button[-1].click().run()                      # "Descartar"
    assert servicios_falsos["estado"] == (2, "Descartada", "Descartada desde la bandeja")


def test_analizar_envia_texto_y_link(monkeypatch):
    recibido = {}

    def fake_analizar(url=None, text=None):
        recibido.update(url=url, text=text)
        from app.schemas import AnalyzeJobResponse
        return AnalyzeJobResponse(source="manual_text", extraction_status="failed",
                                  registration_status="not_attempted", raw_length=0, error_detail="x")

    monkeypatch.setattr(services, "analizar_oferta", fake_analizar)
    at = _pagina("analizar.py").run()
    at.text_area[0].set_value("Texto de la oferta")
    at.text_input[0].set_value("https://www.linkedin.com/jobs/view/1")
    at.button[0].click().run()
    assert recibido == {"url": "https://www.linkedin.com/jobs/view/1", "text": "Texto de la oferta"}


def test_analizar_rechaza_link_sin_http(monkeypatch):
    monkeypatch.setattr(services, "analizar_oferta", lambda **k: pytest.fail("no debía analizar"))
    at = _pagina("analizar.py").run()
    at.text_area[0].set_value("Texto")
    at.text_input[0].set_value("linkedin.com/jobs/1")
    at.button[0].click().run()
    assert "http" in at.error[0].value


def test_que_estudiar_muestra_ranking_y_agrega_al_perfil(monkeypatch):
    guardado = {}
    monkeypatch.setattr(services, "prioridades_estudio", lambda: {"total_ofertas": 3, "prioridades": [
        {"tecnologia": "Airflow", "categoria": "Automation_Tool", "ofertas": 2, "obligatoria_en": 2,
         "demanda": 0.67, "distancia": 1.0, "estado": "Te falta", "tendencia": 1.0,
         "tendencia_txt": "sin datos suficientes", "prioridad": 0.67},
    ]})
    monkeypatch.setattr(services, "cargar_plan_estudio", lambda: None)
    monkeypatch.setattr(services, "guardar_habilidad",
                        lambda *a: guardado.update(args=a))
    at = _pagina("que_estudiar.py").run()
    assert not at.exception
    assert "3 ofertas" in at.warning[0].value
    at.text_input[0].set_value("Proyecto de orquestación en GitHub")
    at.button[1].click().run()                       # "Agregar a mi perfil"
    assert guardado["args"] == ("Airflow", "Automation_Tool", "basico", None, "Proyecto de orquestación en GitHub")


def test_postulaciones_muestra_el_cv_enviado(servicios_falsos, monkeypatch, tmp_path):
    cv = tmp_path / "CV_Alicorp.docx"
    cv.write_bytes(b"x")
    monkeypatch.setattr(services, "versiones_cv", lambda job_id: [
        {"job_id": 2, "version": 1, "fecha": "2026-10-27T10:00:00", "ruta_cv": str(cv),
         "ruta_brechas": "b.docx", "usa_texto_de_pluma": True, "enviado": True,
         "fecha_envio": "2026-10-27T11:00:00"},
    ])
    at = _pagina("postulaciones.py").run()
    assert not at.exception
    assert any("Enviado el 2026-10-27" in m.value for m in at.markdown)  # st.badge se renderiza como markdown
