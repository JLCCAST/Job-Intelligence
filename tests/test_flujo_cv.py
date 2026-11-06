"""
Tests del flujo de adaptar CV: Preguntón -> Pluma -> Notario -> Imprenta.

Se usa el CV de ejemplo (data/cv_base.example.yaml), una oferta
falsa y un Gemini falso; el checkpointer es en memoria y los
archivos se escriben en una carpeta temporal.
"""

import json
import re

import pytest
from docx import Document
from langgraph.checkpoint.memory import InMemorySaver

from app.agents import balanza, batuta, eventos, imprenta, notario, pluma, pregunton
from app.cv import historial
from app.cv import respuestas as modulo_respuestas
from app.cv.cambios import calcular_cambios, diferencias, similitud
from app.cv.cargador import RAIZ, cargar_cv_base
from app.cv.modelo import CVBase
from app.llm import ResultadoEstructurado

CV_EJEMPLO = cargar_cv_base(RAIZ / "data" / "cv_base.example.yaml")

OFERTA = {
    "job_id": 42,
    "puesto": "Analista de Datos Jr",
    "empresa": "Empresa Ficticia",
    "area": "Data_Analytics",
    "match_score": 55.0,
    "cumple_ingles": True,
    "requisitos": [
        {"nombre": "Python", "requirement_type": "required", "nivel_pedido": "intermedio",
         "nivel_usuario": "intermedio", "bajo_nivel": False},
        {"nombre": "Power BI", "requirement_type": "required", "nivel_pedido": "unspecified",
         "nivel_usuario": None, "bajo_nivel": False},
        {"nombre": "Airflow", "requirement_type": "required", "nivel_pedido": "basico",
         "nivel_usuario": None, "bajo_nivel": False},
        {"nombre": "dbt", "requirement_type": "preferred", "nivel_pedido": "unspecified",
         "nivel_usuario": None, "bajo_nivel": False},
        {"nombre": "Inglés", "requirement_type": "required", "nivel_pedido": "intermedio",
         "nivel_usuario": None, "bajo_nivel": False},
    ],
}

REDACCION_LIMPIA = {
    "perfil": "Estudiante de Ingeniería de Sistemas orientado a BI con SQL, Python, Power BI y dbt.",
    "experiencia": [{"indice": 0, "logros": ["Automaticé en Python un reporte semanal que tomaba 3 horas manuales."]}],
    "proyectos": [{"indice": 0, "logros": ["Modelé un esquema estrella en SQL Server y un dashboard en Power BI con 8 KPIs."]}],
    "habilidades_destacadas": ["Power BI", "SQL", "dbt"],
}
REDACCION_CON_AIRFLOW = {**REDACCION_LIMPIA, "perfil": "Analista con experiencia en Airflow y Python."}


# --------- Preguntón ---------

def test_pregunton_solo_pregunta_lo_que_no_esta_en_perfil_cv_ni_respuestas():
    preguntas = pregunton.armar_preguntas(
        OFERTA["requisitos"], skills_cv=CV_EJEMPLO.skills_declaradas(), ya_respondidas=set()
    )
    # Python: en el perfil. Power BI: en el CV. Inglés: no se pregunta.
    assert [p["tecnologia"] for p in preguntas] == ["Airflow", "dbt"]
    assert "obligatorio (nivel basico)" in preguntas[0]["texto"]


def test_pregunton_no_repite_lo_ya_respondido():
    preguntas = pregunton.armar_preguntas(
        OFERTA["requisitos"], skills_cv=CV_EJEMPLO.skills_declaradas(), ya_respondidas={"airflow"}
    )
    assert [p["tecnologia"] for p in preguntas] == ["dbt"]


# --------- Pluma ---------

def test_seleccion_pone_primero_el_proyecto_mas_relevante():
    cv = CVBase.model_validate({
        "contacto": {"nombre": "X", "email": "x@x.com"},
        "perfil": "p",
        "proyectos": [
            {"nombre": "Planilla", "logros": ["Hice una planilla."], "stack": ["Excel"]},
            {"nombre": "Dashboard", "logros": ["Otro logro.", "Dashboard en Power BI."], "stack": ["Power BI"]},
        ],
    })
    seleccion = pluma.calcular_seleccion(cv, OFERTA)
    assert [p["indice"] for p in seleccion["proyectos"]] == [1, 0]
    # Dentro del proyecto, el bullet que menciona la oferta va primero.
    assert seleccion["proyectos"][0]["logros"] == [1, 0]


def _seleccion_ejemplo():
    return pluma.calcular_seleccion(CV_EJEMPLO, OFERTA)


def test_validador_acepta_redaccion_limpia():
    confirmadas = [{"tecnologia": "dbt", "la_tengo": True}]
    assert pluma.encontrar_violaciones(CV_EJEMPLO, OFERTA, _seleccion_ejemplo(), REDACCION_LIMPIA, confirmadas) == []


def test_validador_rechaza_tecnologia_no_confirmada():
    violaciones = pluma.encontrar_violaciones(CV_EJEMPLO, OFERTA, _seleccion_ejemplo(), REDACCION_CON_AIRFLOW, [])
    assert any("Airflow" in v for v in violaciones)


def test_validador_rechaza_cifras_inventadas():
    inventada = {**REDACCION_LIMPIA, "proyectos": [{"indice": 0, "logros": ["Reduje el tiempo de reporte en 45%."]}]}
    confirmadas = [{"tecnologia": "dbt", "la_tengo": True}]
    violaciones = pluma.encontrar_violaciones(CV_EJEMPLO, OFERTA, _seleccion_ejemplo(), inventada, confirmadas)
    assert any("45" in v for v in violaciones)


def test_validador_rechaza_indices_cambiados():
    cambiada = {**REDACCION_LIMPIA, "proyectos": [{"indice": 3, "logros": ["x"]}]}
    confirmadas = [{"tecnologia": "dbt", "la_tengo": True}]
    violaciones = pluma.encontrar_violaciones(CV_EJEMPLO, OFERTA, _seleccion_ejemplo(), cambiada, confirmadas)
    assert any("índices" in v for v in violaciones)


def test_validador_rechaza_bullets_juntados_o_divididos():
    # Si Pluma parte un bullet en dos, ya no se puede comparar cada
    # bullet nuevo con su original en la revisión de cambios.
    partida = {**REDACCION_LIMPIA, "proyectos": [{"indice": 0, "logros": ["Modelé un esquema estrella.", "Hice un dashboard."]}]}
    confirmadas = [{"tecnologia": "dbt", "la_tengo": True}]
    violaciones = pluma.encontrar_violaciones(CV_EJEMPLO, OFERTA, _seleccion_ejemplo(), partida, confirmadas)
    assert any("se esperaban 1 bullets y llegaron 2" in v for v in violaciones)


# --------- Cambios de la IA (sin LLM) ---------

def test_cambios_lista_solo_lo_que_pluma_reescribio_con_su_original():
    confirmadas = [{"tecnologia": "dbt", "la_tengo": True}]
    cambios = calcular_cambios(CV_EJEMPLO, OFERTA, _seleccion_ejemplo(), REDACCION_LIMPIA, confirmadas)
    por_id = {c["id"]: c for c in cambios}
    assert set(por_id) == {"perfil", "experiencia-0-0", "proyectos-0-0"}

    proyecto = por_id["proyectos-0-0"]
    assert proyecto["original"] == CV_EJEMPLO.proyectos[0].logros[0]
    assert proyecto["item"] == "Dashboard de Ventas"
    # El perfil nuevo menciona dbt (confirmado) y BI: el motivo calculado lo dice.
    assert "dbt" in por_id["perfil"]["motivo"]
    assert por_id["perfil"]["motivo_de"] == "calculado"


def test_un_texto_identico_no_es_un_cambio():
    igual = {**REDACCION_LIMPIA, "perfil": CV_EJEMPLO.perfil}
    cambios = calcular_cambios(CV_EJEMPLO, OFERTA, _seleccion_ejemplo(), igual, [])
    assert "perfil" not in {c["id"] for c in cambios}


def test_diferencias_marca_palabras_quitadas_y_agregadas():
    partes = diferencias("Hice un reporte en Excel.", "Hice un dashboard en Power BI.")
    assert "".join(p["texto"] for p in partes if p["tipo"] != "quitado") == "Hice un dashboard en Power BI."
    assert "".join(p["texto"] for p in partes if p["tipo"] != "agregado") == "Hice un reporte en Excel."
    assert {"tipo": "agregado", "texto": "dashboard "} in partes


def test_similitud_distingue_un_retoque_de_una_reescritura():
    assert similitud("Apoyo en la gestión de inventarios.", "Apoyé en la gestión de inventarios.") >= 0.8
    assert similitud("Estudiante con interés en datos.", "Analista orientado a BI con Power BI y SQL Server.") < 0.5


def test_notario_verifica_lo_que_afirma():
    cambio = {
        "id": "proyectos-0-0", "original": "Hice un reporte.", "nuevo": "Hice un dashboard en Power BI.",
        "motivo": "calculado", "motivo_de": "calculado", "requisitos": [], "atencion": None, "alerta": None,
    }
    explicaciones = [{
        "id": "proyectos-0-0", "motivo": "Agregué Power BI porque la oferta lo pide.",
        "requisitos": ["Power BI", "Tableau", "Python"], "revisar": None,
    }]
    [c] = notario.aplicar_explicaciones([cambio], explicaciones, OFERTA)
    assert c["motivo_de"] == "notario"
    assert c["requisitos"] == ["Power BI"]                 # el único citado que es cierto
    assert "«Tableau», pero la oferta no lo pide" in c["alerta"]
    assert "«Python», pero el texto nuevo no lo menciona" in c["alerta"]


def test_un_cambio_sin_explicacion_conserva_el_motivo_calculado():
    cambio = {"id": "perfil", "nuevo": "x", "motivo": "Reformulado con otras palabras.", "motivo_de": "calculado"}
    assert notario.aplicar_explicaciones([cambio], [], OFERTA) == [cambio]


# --------- Flujo completo con Batuta ---------

def _fake_notario(prompt, schema, agente):
    """Notario falso: explica cada cambio que aparece en el prompt."""
    ids = re.findall(r"\[id=([^\]]+)\]", prompt)
    datos = {"explicaciones": [
        {"id": i, "motivo": f"Explicación de {i}.", "requisitos": [], "revisar": None} for i in ids
    ]}
    return ResultadoEstructurado(success=True, data=schema.model_validate(datos))


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    """CV de ejemplo, oferta falsa, Gemini falso, archivos en tmp."""
    redacciones = []  # cola de lo que "responde" Gemini, en orden

    def fake_gemini(prompt, schema, agente):
        datos = redacciones.pop(0) if len(redacciones) > 1 else redacciones[0]
        return ResultadoEstructurado(success=True, data=schema.model_validate(datos))

    for modulo in (pregunton, pluma, notario, imprenta):
        monkeypatch.setattr(modulo, "cargar_cv_base", lambda: CV_EJEMPLO)
    monkeypatch.setattr(balanza, "leer_oferta_para_cv", lambda job_id: OFERTA)
    monkeypatch.setattr(pluma, "generar_estructurado", fake_gemini)
    monkeypatch.setattr(notario, "generar_estructurado", _fake_notario)
    monkeypatch.setattr(modulo_respuestas, "RUTA_RESPUESTAS", tmp_path / "respuestas.yaml")
    monkeypatch.setattr(imprenta, "CARPETA_SALIDAS", tmp_path / "salidas")
    monkeypatch.setattr(historial, "RUTA_HISTORIAL", tmp_path / "historial_cv.json")
    monkeypatch.setattr(eventos, "RUTA_ACTIVIDAD", tmp_path / "actividad.jsonl")

    grafo = batuta.construir_grafo_cv(InMemorySaver())
    return grafo, redacciones, tmp_path


def _texto_docx(ruta) -> str:
    doc = Document(ruta)
    partes = [p.text for p in doc.paragraphs]
    partes += [c.text for t in doc.tables for fila in t.rows for c in fila.cells]
    return "\n".join(partes)


RESPUESTAS = [
    {"tecnologia": "Airflow", "la_tengo": False},
    {"tecnologia": "dbt", "la_tengo": True, "nivel": "basico", "donde": "Curso de dbt"},
]


def test_flujo_pausa_corrige_y_genera_los_dos_docx(entorno):
    grafo, redacciones, tmp_path = entorno
    # 1er intento inventa Airflow -> el validador lo rechaza -> 2do intento limpio.
    redacciones += [REDACCION_CON_AIRFLOW, REDACCION_LIMPIA]

    r = batuta.iniciar_cv(42, grafo=grafo)
    assert r["esperando_respuestas"]
    assert [p["tecnologia"] for p in r["preguntas"]] == ["Airflow", "dbt"]

    r = batuta.responder_cv(r["thread_id"], RESPUESTAS, grafo=grafo)
    assert not r["esperando_respuestas"]
    assert r["estado"]["intentos"] == 2
    assert r["estado"]["violaciones"] == []

    # Notario explicó los cambios y el flujo espera tu revisión.
    assert r["esperando_revision"]
    assert {c["id"] for c in r["cambios"]} == {"perfil", "experiencia-0-0", "proyectos-0-0"}
    assert all(c["motivo_de"] == "notario" for c in r["cambios"])
    assert r["estado"].get("ruta_cv") is None           # todavía no hay Word

    r = batuta.revisar_cv(r["thread_id"], [], grafo=grafo)   # aceptas todo
    estado = r["estado"]
    assert not r["esperando_revision"]

    cv = _texto_docx(estado["ruta_cv"])
    assert "Modelé un esquema estrella" in cv          # texto de Pluma
    assert "Airflow" not in cv
    assert estado["ruta_cv"].endswith("CV_Empresa_Ficticia_Analista_de_Datos_Jr.docx")

    brechas = _texto_docx(estado["ruta_brechas"])
    assert "Airflow (obligatorio): no aparece en tu perfil." in brechas
    assert "Confirmado en Preguntón" in brechas        # dbt
    assert "En tu CV (no en tu perfil)" in brechas     # Power BI

    # Las respuestas quedaron guardadas: la siguiente vez no pregunta.
    assert len(modulo_respuestas.cargar_respuestas()) == 2
    r2 = batuta.iniciar_cv(42, grafo=grafo)
    assert not r2["esperando_respuestas"]
    assert r2["esperando_revision"]                    # va directo a la revisión


def test_un_cambio_rechazado_vuelve_a_tu_texto_original(entorno):
    grafo, redacciones, tmp_path = entorno
    redacciones.append(REDACCION_LIMPIA)
    r = batuta.iniciar_cv(42, grafo=grafo)
    r = batuta.responder_cv(r["thread_id"], RESPUESTAS, grafo=grafo)
    r = batuta.revisar_cv(r["thread_id"], ["perfil", "id-que-no-existe"], grafo=grafo)
    estado = r["estado"]

    cv = _texto_docx(estado["ruta_cv"])
    assert CV_EJEMPLO.perfil in cv                      # rechazado: tu perfil original
    assert REDACCION_LIMPIA["perfil"] not in cv
    assert "Modelé un esquema estrella" in cv           # aceptado: texto de Pluma
    assert estado["rechazados"] == ["perfil"]           # los ids desconocidos se ignoran

    # Queda registro de qué cambió la IA y qué decidiste.
    guardado = json.loads((tmp_path / "salidas").rglob("cambios.json").__next__().read_text(encoding="utf-8"))
    aceptados = {c["id"]: c["aceptado"] for c in guardado["cambios"]}
    assert aceptados == {"perfil": False, "experiencia-0-0": True, "proyectos-0-0": True}
    assert historial.versiones(42)[0]["revision"]["aceptados"] == 2


def test_si_notario_falla_el_flujo_sigue_con_motivos_calculados(entorno, monkeypatch):
    grafo, redacciones, _ = entorno
    redacciones.append(REDACCION_LIMPIA)
    monkeypatch.setattr(notario, "generar_estructurado",
                        lambda *a, **k: ResultadoEstructurado(success=False, error="429 PerDay"))
    r = batuta.iniciar_cv(42, grafo=grafo)
    r = batuta.responder_cv(r["thread_id"], RESPUESTAS, grafo=grafo)

    assert r["esperando_revision"]
    assert "429" in r["notario_error"]
    assert all(c["motivo_de"] == "calculado" for c in r["cambios"])
    r = batuta.revisar_cv(r["thread_id"], [], grafo=grafo)
    assert r["estado"]["ruta_cv"]


def test_si_pluma_no_cambia_nada_no_hay_revision(entorno):
    grafo, redacciones, _ = entorno
    sin_cambios = {
        "perfil": CV_EJEMPLO.perfil,
        "experiencia": [{"indice": 0, "logros": list(CV_EJEMPLO.experiencia[0].logros)}],
        "proyectos": [{"indice": 0, "logros": list(CV_EJEMPLO.proyectos[0].logros)}],
        "habilidades_destacadas": ["SQL"],
    }
    redacciones.append(sin_cambios)
    r = batuta.iniciar_cv(42, grafo=grafo)
    r = batuta.responder_cv(r["thread_id"], RESPUESTAS, grafo=grafo)
    assert not r["esperando_revision"]
    assert r["estado"]["ruta_cv"]


def test_si_pluma_nunca_pasa_el_validador_usa_tus_bullets_originales(entorno):
    grafo, redacciones, _ = entorno
    redacciones.append(REDACCION_CON_AIRFLOW)  # siempre inventa

    r = batuta.iniciar_cv(42, grafo=grafo)
    r = batuta.responder_cv(r["thread_id"], RESPUESTAS, grafo=grafo)
    estado = r["estado"]

    # Sin texto de la IA no hay nada que revisar: va directo a Imprenta.
    assert not r["esperando_revision"]
    assert estado["intentos"] == pluma.MAX_INTENTOS
    assert estado["violaciones"]
    cv = _texto_docx(estado["ruta_cv"])
    assert "Airflow" not in cv
    assert CV_EJEMPLO.proyectos[0].logros[0] in cv     # bullet original
    assert "no pasó el validador" in _texto_docx(estado["ruta_brechas"])


def test_cada_adaptacion_crea_una_version_nueva_sin_pisar_la_anterior(entorno):
    grafo, redacciones, _ = entorno
    redacciones.append(REDACCION_LIMPIA)
    r = batuta.iniciar_cv(42, grafo=grafo)
    r = batuta.responder_cv(r["thread_id"], RESPUESTAS, grafo=grafo)
    r1 = batuta.revisar_cv(r["thread_id"], [], grafo=grafo)["estado"]
    r = batuta.iniciar_cv(42, grafo=grafo)                   # ya no pregunta
    r2 = batuta.revisar_cv(r["thread_id"], [], grafo=grafo)["estado"]

    assert r1["ruta_cv"] != r2["ruta_cv"]
    versiones = historial.versiones(42)
    assert [v["version"] for v in versiones] == [2, 1]
    assert all(v["usa_texto_de_pluma"] for v in versiones)


def test_en_vivo_se_ve_cada_agente_la_pausa_y_el_rechazo_del_validador(entorno):
    grafo, redacciones, _ = entorno
    redacciones += [REDACCION_CON_AIRFLOW, REDACCION_LIMPIA]

    primera = list(batuta.iniciar_cv_en_vivo(42, grafo=grafo))
    fines = [e for e in primera if e["tipo"] == "fin"]
    assert [e["agente"] for e in fines] == ["balanza", "pregunton"]
    assert fines[-1]["estado"] == "pausa" and "2 preguntas" in fines[-1]["resumen"]
    resumen = primera[-1]["resumen"]
    assert primera[-1]["tipo"] == "_resumen" and resumen["esperando_respuestas"]

    segunda = list(batuta.responder_cv_en_vivo(resumen["thread_id"], RESPUESTAS, grafo=grafo))
    pasos = [(e["agente"], e["estado"]) for e in segunda if e["tipo"] == "fin"]
    assert pasos == [
        ("pregunton", "ok"), ("pluma", "ok"), ("pluma", "ok"),
        ("validador", "rechazo"),      # Pluma inventó Airflow: se ve el rechazo
        ("pluma", "ok"), ("validador", "ok"),
        ("notario", "ok"), ("notario", "pausa"),   # explica los cambios y espera tu revisión
    ]
    assert "3 cambios" in [e for e in segunda if e["tipo"] == "fin"][-1]["resumen"]
    assert segunda[-1]["resumen"]["esperando_revision"]
    # Cada "fin" viene después de su "inicio".
    tipos = [(e["tipo"], e["nodo"]) for e in segunda if e["tipo"] in ("inicio", "fin")]
    assert tipos[0] == ("inicio", "pregunton") and tipos[1] == ("fin", "pregunton")

    tercera = list(batuta.revisar_cv_en_vivo(resumen["thread_id"], ["perfil"], grafo=grafo))
    fines = [e for e in tercera if e["tipo"] == "fin"]
    assert [(e["agente"], e["estado"]) for e in fines] == [("notario", "ok"), ("imprenta", "ok")]
    assert "1 cambio rechazado vuelve" in fines[0]["resumen"]
    assert len(eventos.actividad_reciente()) == len([e for e in primera + segunda + tercera if e["tipo"] == "fin"])
