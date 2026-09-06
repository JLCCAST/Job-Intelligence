"""
matcher.py

Responsabilidad única: dado el nombre de una tecnología extraída
por Gemini, resolverlo contra el catálogo normalizado en la BD.

Nivel 1 (automático, sin intervención): coincide con un alias
existente o con un nombre canónico existente -> se usa ese id.

Nivel 2 (semi-automático): no coincide con nada -> se crea como
tecnología nueva. Si la confianza de Gemini fue baja, se marca
`necesita_revision=True` para que la revises luego desde tu propio
perfil de datos, sin que esto bloquee el resto del pipeline.
"""

import os
from dataclasses import dataclass

import psycopg2

from app.schemas import ExtractedTechnology

# Por debajo de este umbral, una tecnología nueva se crea igual
# (no bloqueamos el flujo) pero queda marcada para que la revises.
CONFIDENCE_AUTOCREATE_THRESHOLD = 0.75


def _get_connection():
    return psycopg2.connect(os.environ["SUPABASE_DB_URL"])


@dataclass
class MatchResult:
    technology_id: int
    was_created: bool
    needs_review: bool


def match_or_create_technology(tech: ExtractedTechnology) -> MatchResult:
    nombre_normalizado = tech.name.strip().lower()

    conn = _get_connection()
    try:
        with conn:  # maneja commit/rollback de la transacción, NO cierra el socket
            with conn.cursor() as cur:
                # Nivel 1a: ¿coincide con un alias ya conocido?
                cur.execute(
                    "SELECT technology_id FROM technology_alias WHERE LOWER(alias_texto) = %s",
                    (nombre_normalizado,),
                )
                row = cur.fetchone()
                if row:
                    return MatchResult(technology_id=row[0], was_created=False, needs_review=False)

                # Nivel 1b: ¿coincide con un nombre canónico ya existente?
                cur.execute(
                    "SELECT technology_id FROM technology WHERE LOWER(nombre_canonico) = %s",
                    (nombre_normalizado,),
                )
                row = cur.fetchone()
                if row:
                    return MatchResult(technology_id=row[0], was_created=False, needs_review=False)

                # Nivel 2: no existe -- se crea. needs_review depende de
                # la confianza que Gemini reportó para esta extracción.
                needs_review = tech.confidence < CONFIDENCE_AUTOCREATE_THRESHOLD
                cur.execute(
                    """
                    INSERT INTO technology (nombre_canonico, categoria, necesita_revision)
                    VALUES (%s, %s, %s)
                    RETURNING technology_id
                    """,
                    (tech.name, tech.category, needs_review),
                )
                new_id = cur.fetchone()[0]

                # Guardamos también el texto exacto como su propio alias,
                # para que la PRÓXIMA vez que aparezca ("python" en
                # minúscula, por ejemplo) calce directo en el Nivel 1a
                # sin volver a crear un duplicado.
                cur.execute(
                    """
                    INSERT INTO technology_alias (technology_id, alias_texto)
                    VALUES (%s, %s)
                    ON CONFLICT (alias_texto) DO NOTHING
                    """,
                    (new_id, nombre_normalizado),
                )

        return MatchResult(technology_id=new_id, was_created=True, needs_review=needs_review)
    finally:
        # ESTO es lo que faltaba: sin este close(), la conexión queda
        # viva después de que la función termina, y te comes el límite
        # de conexiones del pooler de Supabase en un par de llamadas.
        conn.close()