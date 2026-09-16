"""
Tests de matcher.py con cursor falso (sin tocar Supabase).

Verifican la lógica de niveles y, sobre todo, que la función NO
abra conexión propia -- eso es lo que permite que forme parte de
la transacción del job.
"""

import inspect

import pytest

from app.matcher import (
    match_or_create_technology,
    CONFIDENCE_AUTOCREATE_THRESHOLD,
)
from app.schemas import ExtractedTechnology
from tests.test_repository import CursorFalso


def _tech(name="Python", confidence=1.0):
    return ExtractedTechnology(
        name=name,
        category="Programming",
        requirement_type="required",
        level="avanzado",
        confidence=confidence,
        evidence_text="conocimientos avanzados de Python",
    )


def test_recibe_cursor_y_no_abre_conexion():
    # Si alguien vuelve a meterle _get_connection() adentro, esto falla:
    # se rompería la atomicidad del insert del job.
    params = list(inspect.signature(match_or_create_technology).parameters)
    assert params[0] == "cur"

    fuente = inspect.getsource(match_or_create_technology)
    assert "_get_connection" not in fuente


def test_nivel_1a_encuentra_por_alias():
    cur = CursorFalso([(10,)])
    r = match_or_create_technology(cur, _tech())

    assert r.technology_id == 10
    assert r.was_created is False
    assert r.needs_review is False
    assert len(cur.consultas) == 1


def test_nivel_1b_encuentra_por_nombre_canonico():
    cur = CursorFalso([None, (20,)])
    r = match_or_create_technology(cur, _tech())

    assert r.technology_id == 20
    assert r.was_created is False
    assert not cur.hubo_insert_en("technology")


def test_nivel_2_crea_con_confianza_alta_sin_revision():
    cur = CursorFalso([None, None, (30,)])
    r = match_or_create_technology(cur, _tech(confidence=0.95))

    assert r.technology_id == 30
    assert r.was_created is True
    assert r.needs_review is False
    assert cur.hubo_insert_en("technology_alias")


def test_nivel_2_con_confianza_baja_marca_revision():
    baja = CONFIDENCE_AUTOCREATE_THRESHOLD - 0.01
    cur = CursorFalso([None, None, (31,)])
    r = match_or_create_technology(cur, _tech(confidence=baja))

    assert r.needs_review is True

    # El flag necesita_revision debe ir en el INSERT a technology.
    insert = next(p for sql, p in cur.consultas if "INSERT INTO technology (" in sql)
    assert insert[-1] is True


def test_alias_se_guarda_en_minusculas():
    cur = CursorFalso([None, None, (40,)])
    match_or_create_technology(cur, _tech(name="PostgreSQL"))

    _, params = cur.consultas[-1]
    assert params == (40, "postgresql")
