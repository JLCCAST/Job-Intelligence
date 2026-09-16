"""
repository.py

Responsabilidad única: hablar con Supabase. Es la ÚNICA capa que
sabe de SQL para `company`, `source` y `job`. Quien la llama
(main.py) trabaja con ids, no con tablas.

Dos patrones distintos a propósito:

- `company` es un catálogo ABIERTO: no se pueden enumerar todas
  las empresas, así que se crea la que no exista (mismo Nivel 1 /
  Nivel 2 de matcher.py, con `company_alias` para no fragmentar).

- `source` es un catálogo CERRADO: son 6 filas sembradas en el
  schema, y tanto el Literal de JobExtraction como
  source_resolver.py solo producen esos valores. Por eso acá NO
  hay "create": si no se encuentra, es un bug de sincronización
  entre código y BD, y conviene que reviente ahora y no que
  inserte una fila basura que nadie note.
"""

import os
from dataclasses import dataclass
from typing import Optional

import psycopg2

from app.matcher import match_or_create_technology
from app.schemas import JobExtraction

# Gemini devuelve este valor cuando la oferta no da el nombre de la
# empresa (ej. "importante empresa del rubro retail").
VALOR_EMPRESA_NO_ESPECIFICADA = "no_especificado"

# Todas esas ofertas anónimas apuntan a UNA sola fila centinela, en
# vez de crear una fila por cada variante de texto vago. Se lee
# decente en Power BI, a diferencia de guardar 'no_especificado'.
EMPRESA_CENTINELA = "No especificada"


def get_connection():
    """
    Conexión nueva contra Supabase.

    Pública porque insert_job_with_technologies necesita abrir UNA
    conexión y pasar el mismo cursor a varias operaciones (para que
    todo el insert del job sea una sola transacción).
    """
    return psycopg2.connect(os.environ["SUPABASE_DB_URL"])


class SourceDesconocida(Exception):
    """El nombre de fuente no existe en el catálogo `source`."""


# --------------------------------------------------------------
# COMPANY (catálogo abierto: se crea lo que no exista)
# --------------------------------------------------------------

def _normalizar_nombre_empresa(nombre: Optional[str]) -> str:
    """
    Decide el nombre canónico con el que se va a guardar/buscar.

    Función pura (sin BD) a propósito: así se puede testear sola.
    """
    if nombre is None:
        return EMPRESA_CENTINELA

    limpio = nombre.strip()
    if not limpio or limpio.lower() == VALOR_EMPRESA_NO_ESPECIFICADA:
        return EMPRESA_CENTINELA

    return limpio


def get_or_create_company(cur, nombre: Optional[str]) -> int:
    """
    Devuelve el company_id del nombre dado, creándolo si no existe.

    Recibe un CURSOR, no abre conexión propia: así esta llamada
    puede formar parte de la misma transacción que el insert del
    job (o usarse sola, ver `resolver_company_id`).

    Nivel 1a: coincide con un alias conocido      -> ese id
    Nivel 1b: coincide con un nombre canónico     -> ese id
    Nivel 2 : no existe -> se crea + se guarda su propio alias
    """
    nombre_canonico = _normalizar_nombre_empresa(nombre)
    nombre_normalizado = nombre_canonico.lower()

    # Nivel 1a: ¿ya hay un alias con ese texto?
    cur.execute(
        "SELECT company_id FROM company_alias WHERE LOWER(alias_texto) = %s",
        (nombre_normalizado,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    # Nivel 1b: ¿coincide con un nombre canónico existente?
    cur.execute(
        "SELECT company_id FROM company WHERE LOWER(nombre) = %s",
        (nombre_normalizado,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    # Nivel 2: no existe -> crear.
    cur.execute(
        "INSERT INTO company (nombre) VALUES (%s) RETURNING company_id",
        (nombre_canonico,),
    )
    new_id = cur.fetchone()[0]

    # Se guarda el texto exacto como su primer alias, para que la
    # próxima vez que llegue igual calce en Nivel 1a sin duplicar
    # (mismo truco que matcher.py con technology_alias).
    cur.execute(
        """
        INSERT INTO company_alias (company_id, alias_texto)
        VALUES (%s, %s)
        ON CONFLICT (alias_texto) DO NOTHING
        """,
        (new_id, nombre_normalizado),
    )

    return new_id


# --------------------------------------------------------------
# SOURCE (catálogo cerrado: solo lectura)
# --------------------------------------------------------------

def get_source_id(cur, nombre: str) -> int:
    """
    Devuelve el source_id del nombre dado.

    NO crea. Si no existe, lanza SourceDesconocida: significa que
    el catálogo en BD y el código se desincronizaron, y es mejor
    enterarse ahora.
    """
    cur.execute(
        "SELECT source_id FROM source WHERE nombre = %s",
        (nombre,),
    )
    row = cur.fetchone()
    if row is None:
        raise SourceDesconocida(
            f"La fuente {nombre!r} no existe en la tabla `source`. "
            "Revisa que el catálogo en Supabase, el Literal de "
            "JobExtraction y DOMINIO_A_SOURCE estén sincronizados."
        )
    return row[0]


# --------------------------------------------------------------
# Helpers para usar estas funciones de forma suelta
# --------------------------------------------------------------

def resolver_company_id(nombre: Optional[str]) -> int:
    """
    Versión autónoma de get_or_create_company (abre y cierra su
    propia conexión). Útil para probar desde consola.

    El `finally: conn.close()` NO es opcional: `with conn:` maneja
    commit/rollback pero deja el socket vivo, y el pooler de
    Supabase se queda sin conexiones en pocas llamadas.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                return get_or_create_company(cur, nombre)
    finally:
        conn.close()


def resolver_source_id(nombre: str) -> int:
    """Versión autónoma de get_source_id."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                return get_source_id(cur, nombre)
    finally:
        conn.close()


# --------------------------------------------------------------
# STATUS (catálogo cerrado, igual que source)
# --------------------------------------------------------------

class StatusDesconocido(Exception):
    """El nombre de estado no existe en el catálogo `status`."""


STATUS_INICIAL = "Registrada"


def get_status_id(cur, nombre: str) -> int:
    """Devuelve el status_id. NO crea: `status` también es cerrado."""
    cur.execute("SELECT status_id FROM status WHERE nombre = %s", (nombre,))
    row = cur.fetchone()
    if row is None:
        raise StatusDesconocido(
            f"El estado {nombre!r} no existe en la tabla `status`."
        )
    return row[0]


# --------------------------------------------------------------
# INSERT COMPLETO DEL JOB (todo en UNA transacción)
# --------------------------------------------------------------

@dataclass
class InsertJobResult:
    job_id: int
    company_id: int
    source_id: int
    tecnologias_vinculadas: int
    tecnologias_creadas: list[str]
    tecnologias_para_revisar: list[str]
    tecnologias_duplicadas: list[str]


def insert_job_with_technologies(
    extraction: JobExtraction,
    source_name: str,
    url: Optional[str] = None,
    descripcion_raw: Optional[str] = None,
    descripcion_limpia: Optional[str] = None,
    status_nombre: str = STATUS_INICIAL,
) -> InsertJobResult:
    """
    Guarda una oferta completa: la empresa, el job, sus tecnologías
    y la primera entrada del historial de estado.

    TODO ocurre en una sola transacción sobre una sola conexión. Si
    cualquier paso falla, no queda nada a medias: ni un job sin sus
    tecnologías, ni tecnologías creadas para un job que no existe.

    `source_name` ya viene resuelto por source_resolver.resolver_source
    (determinístico si hubo URL, de Gemini si fue texto pegado).
    """
    creadas: list[str] = []
    para_revisar: list[str] = []
    duplicadas: list[str] = []

    conn = get_connection()
    try:
        with conn:  # commit al salir OK, rollback si hay excepción
            with conn.cursor() as cur:
                # 1. Catálogos: empresa (se crea si hace falta),
                #    fuente y estado (solo lectura).
                company_id = get_or_create_company(cur, extraction.company_name)
                source_id = get_source_id(cur, source_name)
                status_id = get_status_id(cur, status_nombre)

                # 2. La oferta en sí.
                #    modalidad/ubicacion/fecha_publicacion quedan NULL
                #    (JobExtraction no los extrae todavía) y match_score
                #    es de la Fase 5.
                cur.execute(
                    """
                    INSERT INTO job (
                        company_id, source_id, status_id, puesto, url,
                        area, ingles_requerido,
                        descripcion_raw, descripcion_limpia
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING job_id
                    """,
                    (
                        company_id,
                        source_id,
                        status_id,
                        extraction.job_title,
                        url,
                        extraction.area,
                        extraction.english_level,
                        descripcion_raw,
                        descripcion_limpia,
                    ),
                )
                job_id = cur.fetchone()[0]

                # 3. Primera entrada del historial. Sin esto, el día
                #    que muevas el job a "Postulada" no vas a saber
                #    cuándo se registró originalmente.
                cur.execute(
                    """
                    INSERT INTO job_status_history (job_id, status_id, nota)
                    VALUES (%s, %s, %s)
                    """,
                    (job_id, status_id, "Registro automático desde /analyze-job"),
                )

                # 4. Tecnologías.
                #    job_technology tiene PK (job_id, technology_id), así
                #    que si Gemini devolvió "Python" y "python" por
                #    separado ambas resuelven al MISMO id y el segundo
                #    INSERT reventaría la transacción entera. Por eso se
                #    deduplica: gana la primera mención (con su evidencia).
                ids_ya_vinculados: set[int] = set()

                for tech in extraction.technologies:
                    match = match_or_create_technology(cur, tech)

                    if match.technology_id in ids_ya_vinculados:
                        duplicadas.append(tech.name)
                        continue

                    cur.execute(
                        """
                        INSERT INTO job_technology (
                            job_id, technology_id, requirement_type,
                            level, confidence, evidence_text
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            job_id,
                            match.technology_id,
                            tech.requirement_type,
                            tech.level,
                            tech.confidence,
                            tech.evidence_text,
                        ),
                    )
                    ids_ya_vinculados.add(match.technology_id)

                    if match.was_created:
                        creadas.append(tech.name)
                    if match.needs_review:
                        para_revisar.append(tech.name)

        return InsertJobResult(
            job_id=job_id,
            company_id=company_id,
            source_id=source_id,
            tecnologias_vinculadas=len(ids_ya_vinculados),
            tecnologias_creadas=creadas,
            tecnologias_para_revisar=para_revisar,
            tecnologias_duplicadas=duplicadas,
        )
    finally:
        # Igual que en matcher.py: `with conn:` NO cierra el socket.
        conn.close()


# --------------------------------------------------------------
# Detección de ofertas ya registradas
# --------------------------------------------------------------

def _normalizar_url(url: str) -> str:
    """
    Normalización mínima para comparar URLs: sin espacios y sin
    barra final (`/oferta/1` y `/oferta/1/` son la misma oferta).

    Limitación conocida: no toca query params, así que una misma
    oferta con `?utm_source=...` distinto se vería como nueva.
    """
    return url.strip().rstrip("/")


def buscar_job_por_url(url: Optional[str]) -> Optional[int]:
    """
    Devuelve el job_id si esa URL ya fue registrada, o None.

    Se consulta ANTES de llamar a Gemini: si la oferta ya existe,
    no tiene sentido gastar cuota de la API para descartar el
    resultado después.
    """
    if not url:
        return None

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT job_id FROM job
                    WHERE RTRIM(TRIM(url), '/') = %s
                    ORDER BY job_id
                    LIMIT 1
                    """,
                    (_normalizar_url(url),),
                )
                row = cur.fetchone()
                return row[0] if row else None
    finally:
        conn.close()
