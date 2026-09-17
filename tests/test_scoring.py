"""
Tests de la fórmula del Match Score.

Todos sobre datos inventados, sin BD: la fórmula es pura.
Los números esperados están calculados a mano en cada test, que es
lo único que realmente valida una fórmula (si el test recalcula lo
mismo que el código, no prueba nada).
"""

import pytest

from app.scoring import (
    CREDITO_NIVEL_SUFICIENTE,
    calcular_credito,
    calcular_match_score,
    CREDITO_NIVEL_MENOR,
    PESO_PREFERRED,
    PESO_REQUIRED,
)


def req(tech_id, nombre, tipo="required", level="intermedio"):
    return {
        "technology_id": tech_id,
        "nombre": nombre,
        "requirement_type": tipo,
        "level": level,
    }


# --------- Crédito por nivel (el corazón de la fórmula) ---------

@pytest.mark.parametrize(
    "pedido, mio, esperado",
    [
        ("intermedio", "intermedio", 1.0),   # justo lo pedido
        ("intermedio", "avanzado", 1.0),     # más de lo pedido
        ("avanzado", "intermedio", 0.7),     # menos de lo pedido
        ("avanzado", "basico", 0.7),         # bastante menos, mismo crédito
        ("basico", "avanzado", 1.0),
        ("intermedio", None, 0.0),           # no la tengo
        ("unspecified", "basico", 1.0),      # no pidieron nivel -> basta tenerla
        ("unspecified", None, 0.0),
        (None, "intermedio", 1.0),
    ],
)
def test_calcular_credito(pedido, mio, esperado):
    assert calcular_credito(pedido, mio) == esperado


def test_credito_no_distingue_cuanto_falta():
    # Decisión consciente: faltar un nivel o dos da el mismo crédito.
    # Si algún día eso importa, este test es el que hay que cambiar.
    assert calcular_credito("avanzado", "intermedio") == calcular_credito("avanzado", "basico")


# --------- Score completo ---------

def test_cubro_todo_da_100():
    r = calcular_match_score(
        requisitos=[req(1, "Python"), req(2, "SQL", tipo="preferred")],
        mis_niveles={1: "avanzado", 2: "avanzado"},
    )
    assert r.score == 100.0
    assert r.faltantes == []


def test_no_cubro_nada_da_0():
    r = calcular_match_score(
        requisitos=[req(1, "Python"), req(2, "SQL")],
        mis_niveles={},
    )
    assert r.score == 0.0
    assert r.faltantes == ["Python", "SQL"]


def test_required_pesa_el_doble_que_preferred():
    # Tengo solo la 'required': 1.0*1.0 / (1.0+0.5) = 66.67
    r = calcular_match_score(
        requisitos=[req(1, "Python"), req(2, "Docker", tipo="preferred")],
        mis_niveles={1: "intermedio"},
    )
    assert r.score == 66.67

    # Al revés: tengo solo la 'preferred': 0.5*1.0 / 1.5 = 33.33
    r2 = calcular_match_score(
        requisitos=[req(1, "Python"), req(2, "Docker", tipo="preferred")],
        mis_niveles={2: "intermedio"},
    )
    assert r2.score == 33.33


def test_nivel_menor_aplica_credito_parcial():
    # Piden avanzado, tengo intermedio: 1.0*0.7 / 1.0 = 70.0
    r = calcular_match_score(
        requisitos=[req(1, "Python", level="avanzado")],
        mis_niveles={1: "intermedio"},
    )
    assert r.score == 70.0
    # Sigue contando como cubierta (la tengo), aunque no al nivel pedido.
    assert r.cubiertas == ["Python"]
    assert r.faltantes == []


def test_lo_que_se_y_no_piden_no_sube_el_score():
    # Declaro 5 habilidades pero la oferta solo pide una que no tengo.
    r = calcular_match_score(
        requisitos=[req(9, "Cobol")],
        mis_niveles={1: "avanzado", 2: "avanzado", 3: "avanzado", 4: "avanzado"},
    )
    assert r.score == 0.0


def test_oferta_sin_requisitos_da_none_no_cero():
    # Distinguir "no hay información" de "no calzo en nada".
    r = calcular_match_score(requisitos=[], mis_niveles={1: "avanzado"})
    assert r.score is None


# --------- Inglés ---------

def test_ingles_no_pedido_no_entra_al_calculo():
    r = calcular_match_score(
        requisitos=[req(1, "Python")],
        mis_niveles={1: "intermedio"},
        ingles_requerido="no_especificado",
        mi_nivel_ingles="basico",
    )
    assert r.score == 100.0        # el inglés no arrastró nada
    assert r.cumple_ingles is None  # ni siquiera aplica


def test_ingles_pedido_y_cumplido():
    # Python (1.0) + Inglés (1.0), ambos al 100% -> 100.0
    r = calcular_match_score(
        requisitos=[req(1, "Python")],
        mis_niveles={1: "intermedio"},
        ingles_requerido="intermedio",
        mi_nivel_ingles="avanzado",
    )
    assert r.score == 100.0
    assert r.cumple_ingles is True


def test_ingles_insuficiente_baja_score_y_marca_flag():
    # Python 1.0*1.0 = 1.0 ; Inglés 1.0*0.7 = 0.7 ; total 1.7/2.0 = 85.0
    r = calcular_match_score(
        requisitos=[req(1, "Python")],
        mis_niveles={1: "intermedio"},
        ingles_requerido="avanzado",
        mi_nivel_ingles="intermedio",
    )
    assert r.score == 85.0
    # El score es alto, pero el flag avisa que el inglés NO alcanza:
    # por eso existen los dos, el promedio solo esconde el problema.
    assert r.cumple_ingles is False


def test_ingles_pedido_y_no_declarado():
    r = calcular_match_score(
        requisitos=[req(1, "Python")],
        mis_niveles={1: "intermedio"},
        ingles_requerido="intermedio",
        mi_nivel_ingles=None,
    )
    assert r.score == 50.0   # 1.0 / 2.0
    assert r.cumple_ingles is False
    assert "Inglés" in r.faltantes


def test_solo_piden_ingles():
    r = calcular_match_score(
        requisitos=[],
        mis_niveles={},
        ingles_requerido="basico",
        mi_nivel_ingles="avanzado",
    )
    assert r.score == 100.0


# --------- Caso realista completo ---------

def test_caso_realista():
    """
    Oferta: SQL avanzado (req), Power BI intermedio (req),
            Python básico (pref), Azure intermedio (pref),
            inglés intermedio.
    Perfil: SQL avanzado, Power BI intermedio, Python intermedio,
            sin Azure, inglés intermedio.

    A mano:
      SQL      1.0 * 1.0 = 1.0
      Power BI 1.0 * 1.0 = 1.0
      Python   0.5 * 1.0 = 0.5
      Azure    0.5 * 0.0 = 0.0
      Inglés   1.0 * 1.0 = 1.0
      -------------------------
      aporte = 3.5   peso = 4.0   ->  87.5
    """
    r = calcular_match_score(
        requisitos=[
            req(1, "SQL", level="avanzado"),
            req(2, "Power BI", level="intermedio"),
            req(3, "Python", tipo="preferred", level="basico"),
            req(4, "Azure", tipo="preferred", level="intermedio"),
        ],
        mis_niveles={1: "avanzado", 2: "intermedio", 3: "intermedio"},
        ingles_requerido="intermedio",
        mi_nivel_ingles="intermedio",
    )

    assert r.score == 87.5
    assert r.faltantes == ["Azure"]
    assert r.cumple_ingles is True
    assert sum(i.peso for i in r.items) == PESO_REQUIRED * 3 + PESO_PREFERRED * 2


# --------- Flag de requisito obligatorio bajo nivel ---------

def test_required_bajo_nivel_se_reporta():
    # Piden avanzado, tengo intermedio: suma 0.7 pero debe avisar.
    r = calcular_match_score(
        requisitos=[req(1, "Power BI", level="avanzado")],
        mis_niveles={1: "intermedio"},
    )
    assert r.score == 70.0
    assert r.requisitos_bajo_nivel == ["Power BI"]
    assert r.faltantes == []   # sí la tengo, no es "faltante"


def test_preferred_bajo_nivel_no_se_reporta():
    # Que un "deseable" quede grande no merece alarma.
    r = calcular_match_score(
        requisitos=[req(1, "Azure", tipo="preferred", level="avanzado")],
        mis_niveles={1: "basico"},
    )
    assert r.requisitos_bajo_nivel == []


def test_required_al_nivel_no_se_reporta():
    r = calcular_match_score(
        requisitos=[req(1, "SQL", level="avanzado")],
        mis_niveles={1: "avanzado"},
    )
    assert r.requisitos_bajo_nivel == []


def test_required_que_no_tengo_va_a_faltantes_no_a_bajo_nivel():
    # Son dos problemas distintos y no deben mezclarse.
    r = calcular_match_score(
        requisitos=[req(1, "Cobol", level="avanzado")],
        mis_niveles={},
    )
    assert r.faltantes == ["Cobol"]
    assert r.requisitos_bajo_nivel == []


def test_caso_del_job_real():
    """
    Reproduce el job_id=2 real: 92.5% pero con Power BI required en
    avanzado y el usuario en intermedio. El score se ve bien; el
    flag es lo que revela el problema.
    """
    r = calcular_match_score(
        requisitos=[
            req(1, "Power BI", level="avanzado"),
            req(2, "Power Query", tipo="preferred", level="unspecified"),
            req(3, "Python", tipo="preferred", level="unspecified"),
            req(4, "SQL", level="avanzado"),
        ],
        mis_niveles={1: "intermedio", 2: "intermedio", 3: "intermedio", 4: "avanzado"},
        ingles_requerido="intermedio",
        mi_nivel_ingles="intermedio",
    )
    assert r.score == 92.5
    assert r.faltantes == []
    assert r.requisitos_bajo_nivel == ["Power BI"]
