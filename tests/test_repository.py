"""
Tests de repository.py SIN tocar Supabase.

Se usa un cursor falso que responde lo que le programemos, para
verificar la LÓGICA de decisión (qué nivel se toma, si inserta o
no). La correctitud del SQL contra el motor real se valida aparte,
desde consola, con probar_repository.py.
"""

import pytest

from app.repository import (
    _normalizar_nombre_empresa,
    get_or_create_company,
    get_source_id,
    SourceDesconocida,
    EMPRESA_CENTINELA,
)


class CursorFalso:
    """
    Imita lo mínimo de un cursor psycopg2: execute() guarda la
    consulta y fetchone() devuelve la siguiente respuesta que le
    programamos.
    """

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.consultas = []

    def execute(self, sql, params=None):
        self.consultas.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.respuestas.pop(0)

    def hubo_insert_en(self, tabla):
        return any(
            f"INSERT INTO {tabla}" in sql for sql, _ in self.consultas
        )


# --------- Normalización del nombre (función pura) ---------

@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("Banco Pichincha", "Banco Pichincha"),
        ("  Ferreyros  ", "Ferreyros"),          # se recortan espacios
        ("no_especificado", EMPRESA_CENTINELA),  # centinela
        ("NO_ESPECIFICADO", EMPRESA_CENTINELA),  # sin importar mayúsculas
        ("", EMPRESA_CENTINELA),                 # vacío
        ("   ", EMPRESA_CENTINELA),              # solo espacios
        (None, EMPRESA_CENTINELA),               # ausente
    ],
)
def test_normalizar_nombre_empresa(entrada, esperado):
    assert _normalizar_nombre_empresa(entrada) == esperado


# --------- get_or_create_company ---------

def test_company_nivel_1a_encuentra_por_alias():
    # Primera consulta (alias) devuelve un id -> no debe consultar más.
    cur = CursorFalso([(42,)])

    assert get_or_create_company(cur, "Banco Pichincha") == 42
    assert len(cur.consultas) == 1
    assert not cur.hubo_insert_en("company")


def test_company_nivel_1b_encuentra_por_nombre_canonico():
    # alias: nada -> nombre canónico: id 7
    cur = CursorFalso([None, (7,)])

    assert get_or_create_company(cur, "Ferreyros") == 7
    assert len(cur.consultas) == 2
    assert not cur.hubo_insert_en("company")


def test_company_nivel_2_crea_y_guarda_su_propio_alias():
    # alias: nada -> canónico: nada -> INSERT devuelve id 99
    cur = CursorFalso([None, None, (99,)])

    assert get_or_create_company(cur, "Alicorp") == 99
    assert cur.hubo_insert_en("company")
    assert cur.hubo_insert_en("company_alias")

    # El alias guardado debe ir en minúsculas (para que el Nivel 1a,
    # que compara con LOWER(), calce la próxima vez).
    sql_alias, params_alias = cur.consultas[-1]
    assert params_alias == (99, "alicorp")


def test_company_busca_en_minusculas():
    # La búsqueda debe normalizar, si no "PYTHON" y "python" serían
    # empresas distintas.
    cur = CursorFalso([(5,)])
    get_or_create_company(cur, "BANCO PICHINCHA")

    _, params = cur.consultas[0]
    assert params == ("banco pichincha",)


def test_company_no_especificado_usa_centinela():
    cur = CursorFalso([None, None, (1,)])
    get_or_create_company(cur, "no_especificado")

    # Lo que se INSERTA como nombre canónico es el centinela legible,
    # no el literal 'no_especificado'.
    inserts = [p for sql, p in cur.consultas if "INSERT INTO company " in sql]
    assert inserts[0] == (EMPRESA_CENTINELA,)


# --------- get_source_id ---------

def test_source_encuentra_id():
    cur = CursorFalso([(3,)])
    assert get_source_id(cur, "LinkedIn") == 3
    assert not cur.hubo_insert_en("source")


def test_source_desconocida_lanza_error_en_vez_de_crear():
    cur = CursorFalso([None])

    with pytest.raises(SourceDesconocida) as exc:
        get_source_id(cur, "PortalInventado")

    # El mensaje debe decir qué fuente falló, para poder depurarlo.
    assert "PortalInventado" in str(exc.value)
    assert not cur.hubo_insert_en("source")


# --------- get_status_id ---------

def test_status_encuentra_id():
    from app.repository import get_status_id
    cur = CursorFalso([(1,)])
    assert get_status_id(cur, "Registrada") == 1


def test_status_desconocido_lanza_error():
    from app.repository import get_status_id, StatusDesconocido
    cur = CursorFalso([None])
    with pytest.raises(StatusDesconocido):
        get_status_id(cur, "EstadoInventado")
