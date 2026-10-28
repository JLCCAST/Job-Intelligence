"""
Tests de Brújula: el ranking (demanda × distancia × tendencia) se
calcula sin LLM; el plan usa un Gemini falso.
"""

from datetime import date, timedelta

from docx import Document

from app.agents import brujula
from app.gemini import ResultadoEstructurado

HOY = date(2026, 10, 23)


def _fila(job_id, tech, tipo="required", pedido="unspecified", mi_nivel=None, dias_atras=1, categoria="Other"):
    return {
        "job_id": job_id, "fecha_registro": HOY - timedelta(days=dias_atras), "tecnologia": tech,
        "categoria": categoria, "requirement_type": tipo, "nivel_pedido": pedido, "mi_nivel": mi_nivel,
    }


def _por_nombre(prioridades):
    return {p.tecnologia: p for p in prioridades}


def test_lo_que_cubres_no_aparece_y_lo_que_falta_va_primero():
    filas = [
        _fila(1, "SQL", mi_nivel="avanzado", pedido="intermedio"),
        _fila(1, "Airflow"),
        _fila(2, "Airflow"),
        _fila(2, "dbt", tipo="preferred"),
    ]
    p = brujula.calcular_prioridades(filas, hoy=HOY)
    assert [x.tecnologia for x in p] == ["Airflow", "dbt"]
    assert p[0].demanda == 1.0              # obligatoria en 2 de 2 ofertas
    assert p[1].demanda == 0.25             # deseable (0.5) en 1 de 2
    assert p[0].estado == "Te falta"


def test_distancias_nivel_menor_cv_y_preguntón():
    filas = [
        _fila(1, "Power BI", pedido="avanzado", mi_nivel="intermedio"),
        _fila(1, "Python"),
        _fila(1, "dbt"),
        _fila(1, "Airflow"),
    ]
    p = _por_nombre(brujula.calcular_prioridades(
        filas, skills_cv={"python"}, respuestas_confirmadas={"dbt": "basico"}, hoy=HOY,
    ))
    assert p["Power BI"].distancia == brujula.DISTANCIA_NIVEL_MENOR
    assert p["Python"].distancia == brujula.DISTANCIA_SOLO_EN_CV
    assert "dbt" not in p                    # confirmada en el Preguntón y no piden nivel
    assert p["Airflow"].distancia == brujula.DISTANCIA_NO_LA_TIENES


def test_sin_ofertas_suficientes_no_inventa_tendencia():
    p = brujula.calcular_prioridades([_fila(1, "Airflow")], hoy=HOY)
    assert p[0].tendencia == 1.0
    assert p[0].tendencia_txt == "sin datos suficientes"


def test_tendencia_sube_y_nueva_con_dos_ventanas_completas():
    filas = []
    # 5 ofertas hace 40 días: Spark en 1. 5 ofertas recientes: Spark en 4, dbt en 2 (nueva).
    for j in range(5):
        filas.append(_fila(100 + j, "SQL", mi_nivel="avanzado", dias_atras=40))
        filas.append(_fila(200 + j, "SQL", mi_nivel="avanzado", dias_atras=5))
    filas.append(_fila(100, "Spark", dias_atras=40))
    filas += [_fila(200 + j, "Spark", dias_atras=5) for j in range(4)]
    filas += [_fila(200 + j, "dbt", dias_atras=5) for j in range(2)]

    p = _por_nombre(brujula.calcular_prioridades(filas, hoy=HOY))
    assert p["Spark"].tendencia_txt == "sube"
    assert p["Spark"].tendencia == 1.5       # +0.6 se recorta a +0.5
    assert p["dbt"].tendencia_txt == "nueva"


def test_plan_descarta_tecnologias_que_no_calculo_brujula(monkeypatch):
    top = brujula.calcular_prioridades([_fila(1, "Airflow"), _fila(1, "dbt")], hoy=HOY)
    plan_falso = {
        "resumen": "Empieza por Airflow.",
        "items": [
            {"tecnologia": "Airflow", "por_que": "x", "que_aprender": ["DAGs"], "proyecto": "p", "semanas": 3},
            {"tecnologia": "Kubernetes", "por_que": "x", "que_aprender": ["pods"], "proyecto": "p", "semanas": 4},
        ],
    }
    monkeypatch.setattr(brujula, "generar_estructurado",
                        lambda prompt, schema, agente: ResultadoEstructurado(True, schema.model_validate(plan_falso)))
    plan, error = brujula.generar_plan(top, ["SQL", "Python"])
    assert error is None
    assert [i.tecnologia for i in plan.items] == ["Airflow"]


def test_guardar_cargar_plan_e_informe(tmp_path, monkeypatch):
    top = brujula.calcular_prioridades([_fila(1, "Airflow")], hoy=HOY)
    plan = brujula.PlanEstudio(resumen="Empieza por Airflow.", items=[
        brujula.ItemPlan(tecnologia="Airflow", por_que="Obligatoria en 1 oferta.",
                         que_aprender=["DAGs", "Operadores"], proyecto="Orquestar tu ETL del MEF", semanas=3),
    ])
    ruta_plan = tmp_path / "plan.json"
    brujula.guardar_plan(plan, top, ruta_plan)
    guardado = brujula.cargar_plan(ruta_plan)
    assert guardado["plan"]["items"][0]["tecnologia"] == "Airflow"

    ruta = brujula.generar_informe(top, total_ofertas=1, plan=guardado, carpeta=tmp_path)
    texto = "\n".join(p.text for p in Document(ruta).paragraphs)
    assert "Orquestar tu ETL del MEF" in texto
    assert "orientativo" in texto


def test_habilidades_blandas_no_entran_al_ranking():
    p = brujula.calcular_prioridades(
        [_fila(1, "Comunicación clara", categoria="Soft_Skill"), _fila(1, "Airflow")], hoy=HOY,
    )
    assert [x.tecnologia for x in p] == ["Airflow"]
    assert p[0].demanda == 1.0               # sigue dividiendo entre las ofertas reales
