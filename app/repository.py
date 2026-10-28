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
from dotenv import load_dotenv

from app.matcher import match_or_create_technology
from app.schemas import ExtractedTechnology, JobExtraction
from app.scoring import MatchScoreResult, calcular_match_score

# Gemini devuelve este valor cuando la oferta no da el nombre de la
# empresa (ej. "importante empresa del rubro retail").
VALOR_EMPRESA_NO_ESPECIFICADA = "no_especificado"

# Todas esas ofertas anónimas apuntan a UNA sola fila centinela, en
# vez de crear una fila por cada variante de texto vago. Se lee
# decente en Power BI, a diferencia de guardar 'no_especificado'.
EMPRESA_CENTINELA = "No especificada"

# Antes dependía de que alguien importara gemini.py primero (que es
# quien llamaba a load_dotenv); un script que solo usa la BD fallaba.
load_dotenv()


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


# --------------------------------------------------------------
# PERFIL PROPIO (user_skill)
# --------------------------------------------------------------

def upsert_user_skill(
    cur,
    nombre: str,
    categoria: str,
    level: str,
    meses_experiencia: Optional[int] = None,
    evidencia: Optional[str] = None,
) -> int:
    """
    Declara (o actualiza) una habilidad propia.

    `user_skill.technology_id` es FK a `technology`, así que primero
    hay que resolver/crear la tecnología. Se reutiliza a propósito
    `match_or_create_technology` en vez de duplicar la lógica de
    alias: si mañana mejora el matching, el perfil se beneficia
    igual que el pipeline.

    Se arma un ExtractedTechnology con confidence=1.0 porque esto
    NO viene de Gemini -- lo declaras tú, no hay incertidumbre, y
    por eso nunca queda marcado para revisión.
    """
    tech = ExtractedTechnology(
        name=nombre,
        category=categoria,
        # Estos dos campos no aplican a una habilidad propia (son del
        # contexto oferta<->tecnología), pero el modelo los exige.
        requirement_type="required",
        level=level,
        confidence=1.0,
        evidence_text=evidencia or f"Perfil propio: {nombre}",
    )
    match = match_or_create_technology(cur, tech)

    # PK es technology_id, así que reejecutar el seed actualiza en
    # vez de fallar por clave duplicada.
    cur.execute(
        """
        INSERT INTO user_skill (technology_id, level, meses_experiencia, evidencia)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (technology_id) DO UPDATE SET
            level = EXCLUDED.level,
            meses_experiencia = EXCLUDED.meses_experiencia,
            evidencia = EXCLUDED.evidencia
        """,
        (match.technology_id, level, meses_experiencia, evidencia),
    )
    return match.technology_id


def cargar_perfil(habilidades: list[dict]) -> int:
    """
    Carga una lista de habilidades en una sola transacción.

    Cada dict: {nombre, categoria, level, meses_experiencia?, evidencia?}
    Devuelve cuántas se cargaron.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for h in habilidades:
                    upsert_user_skill(
                        cur,
                        nombre=h["nombre"],
                        categoria=h["categoria"],
                        level=h["level"],
                        meses_experiencia=h.get("meses_experiencia"),
                        evidencia=h.get("evidencia"),
                    )
        return len(habilidades)
    finally:
        conn.close()


# --------------------------------------------------------------
# MATCH SCORE (Fase 5)
# --------------------------------------------------------------

# El inglés se declara en user_skill como una "tecnología" más.
# Se aceptan variantes de escritura porque es el único caso donde
# el nombre lo escribes tú a mano y la tilde se presta a errores.
NOMBRES_INGLES = ("inglés", "ingles", "english")


def _leer_requisitos(cur, job_id: int) -> list[dict]:
    """Qué pide la oferta, desde job_technology."""
    cur.execute(
        """
        SELECT jt.technology_id, t.nombre_canonico,
               jt.requirement_type, jt.level
        FROM job_technology jt
        JOIN technology t ON t.technology_id = jt.technology_id
        WHERE jt.job_id = %s
        ORDER BY t.nombre_canonico
        """,
        (job_id,),
    )
    return [
        {
            "technology_id": r[0],
            "nombre": r[1],
            "requirement_type": r[2],
            "level": r[3],
        }
        for r in cur.fetchall()
    ]


def _leer_mi_perfil(cur) -> dict[int, str]:
    """Lo que tengo, desde user_skill: {technology_id: level}."""
    cur.execute("SELECT technology_id, level FROM user_skill")
    return {r[0]: r[1] for r in cur.fetchall()}


def _leer_mi_nivel_ingles(cur) -> Optional[str]:
    """
    Mi nivel de inglés declarado. Se busca por nombre canónico y
    también por alias, y aceptando variantes con/sin tilde.
    """
    cur.execute(
        """
        SELECT us.level
        FROM user_skill us
        JOIN technology t ON t.technology_id = us.technology_id
        LEFT JOIN technology_alias ta ON ta.technology_id = t.technology_id
        WHERE LOWER(t.nombre_canonico) = ANY(%s)
           OR LOWER(ta.alias_texto) = ANY(%s)
        LIMIT 1
        """,
        (list(NOMBRES_INGLES), list(NOMBRES_INGLES)),
    )
    row = cur.fetchone()
    return row[0] if row else None


def calcular_y_guardar_match_score(job_id: int) -> MatchScoreResult:
    """
    Calcula el Match Score de un job y lo persiste en
    `job.match_score`.

    Se guarda el número para que Power BI (Fase 6) lo lea directo,
    sin tener que reimplementar la fórmula en DAX. La fuente de
    verdad de la fórmula es scoring.py, en un solo lugar.

    Es recalculable: si cambias tu user_skill, vuelves a llamar
    esto y el score se actualiza.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ingles_requerido FROM job WHERE job_id = %s",
                    (job_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"No existe el job_id={job_id}.")
                ingles_requerido = row[0]

                resultado = calcular_match_score(
                    requisitos=_leer_requisitos(cur, job_id),
                    mis_niveles=_leer_mi_perfil(cur),
                    ingles_requerido=ingles_requerido,
                    mi_nivel_ingles=_leer_mi_nivel_ingles(cur),
                )

                cur.execute(
                    "UPDATE job SET match_score = %s WHERE job_id = %s",
                    (resultado.score, job_id),
                )

        return resultado
    finally:
        conn.close()


def recalcular_todos_los_scores() -> list[tuple[int, Optional[float]]]:
    """
    Recalcula el score de TODOS los jobs registrados.

    Se usa después de editar tu perfil: los scores viejos quedaron
    calculados contra el perfil anterior y ya no son comparables
    entre sí.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT job_id FROM job ORDER BY job_id")
                ids = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()

    return [(job_id, calcular_y_guardar_match_score(job_id).score) for job_id in ids]


# --------------------------------------------------------------
# DATOS PARA ADAPTAR EL CV (Fase: Preguntón / Pluma / Imprenta)
# --------------------------------------------------------------

def leer_oferta_para_cv(job_id: int) -> dict:
    """
    Todo lo que el flujo de CV necesita saber de una oferta ya
    registrada: puesto, empresa, área y el desglose del Match Score
    requisito por requisito.

    Devuelve tipos simples (dict/list/str) a propósito: este dict
    viaja en el estado de LangGraph, que se guarda en SQLite entre
    la pregunta del Preguntón y tu respuesta.

    NO guarda el score: solo lo recalcula para leer el desglose.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT j.puesto, c.nombre, j.area, j.ingles_requerido
                FROM job j
                JOIN company c ON c.company_id = j.company_id
                WHERE j.job_id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"No existe el job_id={job_id}.")
            puesto, empresa, area, ingles_requerido = row

            score = calcular_match_score(
                requisitos=_leer_requisitos(cur, job_id),
                mis_niveles=_leer_mi_perfil(cur),
                ingles_requerido=ingles_requerido,
                mi_nivel_ingles=_leer_mi_nivel_ingles(cur),
            )
    finally:
        conn.close()

    return {
        "job_id": job_id,
        "puesto": puesto,
        "empresa": None if empresa == EMPRESA_CENTINELA else empresa,
        "area": area,
        "match_score": score.score,
        "cumple_ingles": score.cumple_ingles,
        "requisitos": [
            {
                "nombre": item.nombre,
                "requirement_type": item.requirement_type,
                "nivel_pedido": item.nivel_pedido,
                "nivel_usuario": item.nivel_usuario,
                "bajo_nivel": item.nombre in score.requisitos_bajo_nivel,
            }
            for item in score.items
        ],
    }
