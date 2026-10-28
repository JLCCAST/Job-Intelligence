"""
consultas.py

Lecturas y cambios simples que necesita la app (Streamlit): listar
ofertas, cambiar su estado, ver y editar tu perfil, revisar el
catálogo. repository.py se queda con el flujo de registrar una
oferta; aquí va todo lo demás.

Todas las funciones devuelven dicts/listas simples, listos para
mostrarse en una tabla.
"""

from typing import Optional

from app.repository import (
    get_connection,
    get_status_id,
    recalcular_todos_los_scores,
    upsert_user_skill,
)


def _filas(cur) -> list[dict]:
    columnas = [d[0] for d in cur.description]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


def _leer(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return _filas(cur)
    finally:
        conn.close()


# --------------------------------------------------------------
# Ofertas y postulaciones
# --------------------------------------------------------------

def listar_ofertas() -> list[dict]:
    return _leer(
        """
        SELECT j.job_id, j.puesto, c.nombre AS empresa, so.nombre AS fuente,
               st.nombre AS estado, j.match_score::float AS match_score,
               j.area, j.fecha_registro, j.url
        FROM job j
        JOIN company c ON c.company_id = j.company_id
        JOIN source so ON so.source_id = j.source_id
        JOIN status st ON st.status_id = j.status_id
        ORDER BY j.fecha_registro DESC
        """
    )


def listar_estados() -> list[str]:
    return [f["nombre"] for f in _leer("SELECT nombre FROM status ORDER BY status_id")]


def cambiar_estado(job_id: int, estado: str, nota: Optional[str] = None) -> None:
    """Actualiza el estado y deja registro en el historial, en una sola transacción."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                status_id = get_status_id(cur, estado)
                cur.execute("UPDATE job SET status_id = %s WHERE job_id = %s", (status_id, job_id))
                if cur.rowcount == 0:
                    raise ValueError(f"No existe el job_id={job_id}.")
                cur.execute(
                    "INSERT INTO job_status_history (job_id, status_id, nota) VALUES (%s, %s, %s)",
                    (job_id, status_id, nota or None),
                )
    finally:
        conn.close()


def historial_estados(job_id: int) -> list[dict]:
    return _leer(
        """
        SELECT h.fecha, s.nombre AS estado, h.nota
        FROM job_status_history h
        JOIN status s ON s.status_id = h.status_id
        WHERE h.job_id = %s
        ORDER BY h.fecha DESC
        """,
        (job_id,),
    )


# --------------------------------------------------------------
# Mi perfil (user_skill)
# --------------------------------------------------------------

def listar_mi_perfil() -> list[dict]:
    return _leer(
        """
        SELECT t.nombre_canonico AS tecnologia, t.categoria, us.level AS nivel,
               us.meses_experiencia, us.evidencia
        FROM user_skill us
        JOIN technology t ON t.technology_id = us.technology_id
        ORDER BY t.categoria, t.nombre_canonico
        """
    )


def guardar_habilidad(
    nombre: str,
    categoria: str,
    nivel: str,
    meses_experiencia: Optional[int] = None,
    evidencia: Optional[str] = None,
) -> None:
    """
    Agrega o actualiza una habilidad y recalcula TODOS los Match
    Score: los anteriores se calcularon con el perfil viejo.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                upsert_user_skill(cur, nombre, categoria, nivel, meses_experiencia, evidencia)
    finally:
        conn.close()
    recalcular_todos_los_scores()


# --------------------------------------------------------------
# Revisión del catálogo
# --------------------------------------------------------------

def tecnologias_para_revisar() -> list[dict]:
    return _leer(
        """
        SELECT t.technology_id, t.nombre_canonico AS tecnologia, t.categoria,
               COUNT(jt.job_id) AS ofertas
        FROM technology t
        LEFT JOIN job_technology jt ON jt.technology_id = t.technology_id
        WHERE t.necesita_revision
        GROUP BY t.technology_id
        ORDER BY ofertas DESC, t.nombre_canonico
        """
    )


def aprobar_tecnologia(technology_id: int) -> None:
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE technology SET necesita_revision = FALSE WHERE technology_id = %s",
                    (technology_id,),
                )
    finally:
        conn.close()


# --------------------------------------------------------------
# Análisis de tus ofertas
# --------------------------------------------------------------

def demanda_tecnologias() -> list[dict]:
    """
    Cuántas de tus ofertas piden cada tecnología (obligatoria o
    deseable) y si está en tu perfil. Es la base de "qué te piden más".
    """
    return _leer(
        """
        SELECT t.nombre_canonico AS tecnologia, t.categoria,
               COUNT(*) FILTER (WHERE jt.requirement_type = 'required')  AS obligatoria,
               COUNT(*) FILTER (WHERE jt.requirement_type = 'preferred') AS deseable,
               COUNT(*) AS total,
               (us.technology_id IS NOT NULL) AS la_tengo
        FROM job_technology jt
        JOIN technology t ON t.technology_id = jt.technology_id
        LEFT JOIN user_skill us ON us.technology_id = t.technology_id
        GROUP BY t.technology_id, us.technology_id
        ORDER BY total DESC, t.nombre_canonico
        """
    )


# --------------------------------------------------------------
# Centinela
# --------------------------------------------------------------

def ofertas_recientes(horas: int = 24) -> list[dict]:
    """Registradas en las últimas `horas`, de mejor a peor Match Score."""
    return _leer(
        """
        SELECT j.job_id, j.puesto, c.nombre AS empresa, so.nombre AS fuente,
               j.match_score::float AS match_score, j.url
        FROM job j
        JOIN company c ON c.company_id = j.company_id
        JOIN source so ON so.source_id = j.source_id
        WHERE j.fecha_registro >= now() - make_interval(hours => %s)
        ORDER BY j.match_score DESC NULLS LAST
        """,
        (horas,),
    )


def postulaciones_sin_movimiento(dias: int = 7) -> list[dict]:
    """
    Ofertas en estado Postulada cuyo último cambio de estado tiene
    más de `dias` días: candidatas a hacer seguimiento.
    """
    return _leer(
        """
        SELECT j.job_id, j.puesto, c.nombre AS empresa,
               MAX(h.fecha) AS ultimo_cambio,
               EXTRACT(DAY FROM now() - MAX(h.fecha))::int AS dias
        FROM job j
        JOIN company c ON c.company_id = j.company_id
        JOIN status s ON s.status_id = j.status_id
        JOIN job_status_history h ON h.job_id = j.job_id
        WHERE s.nombre = 'Postulada'
        GROUP BY j.job_id, c.nombre
        HAVING MAX(h.fecha) < now() - make_interval(days => %s)
        ORDER BY ultimo_cambio
        """,
        (dias,),
    )


# --------------------------------------------------------------
# Brújula
# --------------------------------------------------------------

def requisitos_para_brujula() -> list[dict]:
    """
    Cada requisito de cada oferta (sin las descartadas: si la
    descartaste, no representa lo que buscas), con la fecha de la
    oferta y tu nivel en user_skill (None si no la tienes).
    """
    return _leer(
        """
        SELECT j.job_id, j.fecha_registro, t.nombre_canonico AS tecnologia, t.categoria,
               jt.requirement_type, jt.level AS nivel_pedido, us.level AS mi_nivel
        FROM job_technology jt
        JOIN job j ON j.job_id = jt.job_id
        JOIN status s ON s.status_id = j.status_id
        JOIN technology t ON t.technology_id = jt.technology_id
        LEFT JOIN user_skill us ON us.technology_id = jt.technology_id
        WHERE s.nombre <> 'Descartada'
        """
    )
