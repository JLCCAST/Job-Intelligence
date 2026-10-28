"""
Prueba de insert_job_with_technologies contra la Supabase REAL.

Correr desde la raíz del proyecto, con el venv activo:
    python -m scripts.probar_insert_job

NO llama a Gemini: arma un JobExtraction a mano, para probar solo
la capa de BD sin gastar cuota de la API.

Qué valida:
  1. Que un job completo se guarde (job + historial + tecnologías).
  2. Que "Python" y "python" NO revienten la PK de job_technology
     (deduplicación).
  3. Que si algo falla a mitad, NO quede el job a medias (rollback).
"""

from dotenv import load_dotenv

load_dotenv()

from app.repository import insert_job_with_technologies, get_connection
from app.schemas import JobExtraction, ExtractedTechnology


def tech(name, category="Programming", req="required", conf=1.0):
    return ExtractedTechnology(
        name=name,
        category=category,
        requirement_type=req,
        level="intermedio",
        confidence=conf,
        evidence_text=f"se requiere {name}",
    )


print("=" * 66)
print("1) INSERT COMPLETO")
print("=" * 66)

extraction = JobExtraction(
    job_title="Practicante de BI (PRUEBA)",
    company_name="Banco Pichincha",
    source_name="no_especificado",
    area="BI",
    english_level="intermedio",
    is_offer_available=True,
    technologies=[
        tech("Python"),
        tech("SQL", category="Database"),
        tech("Power BI", category="BI_Tool", req="preferred"),
        # Duplicado a propósito: mismo id que "Python" vía alias.
        tech("python"),
        # Confianza baja -> debería marcarse para revisión si es nueva.
        tech("Power Query", category="BI_Tool", conf=0.60),
    ],
)

r = insert_job_with_technologies(
    extraction=extraction,
    source_name="Career Page",
    url="https://careers.ferreyros.com.pe/job/PRUEBA",
    descripcion_limpia="Texto de prueba de la oferta.",
)

print(f"  job_id                  : {r.job_id}")
print(f"  company_id              : {r.company_id}")
print(f"  source_id               : {r.source_id}")
print(f"  tecnologías vinculadas  : {r.tecnologias_vinculadas}  (esperado: 4)")
print(f"  tecnologías creadas     : {r.tecnologias_creadas}")
print(f"  marcadas para revisar   : {r.tecnologias_para_revisar}")
print(f"  duplicadas ignoradas    : {r.tecnologias_duplicadas}  (esperado: ['python'])")
print()

print("=" * 66)
print("2) VERIFICACIÓN EN BD")
print("=" * 66)

conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM job_technology WHERE job_id = %s", (r.job_id,))
        print(f"  filas en job_technology : {cur.fetchone()[0]}")

        cur.execute("SELECT COUNT(*) FROM job_status_history WHERE job_id = %s", (r.job_id,))
        print(f"  filas en historial      : {cur.fetchone()[0]}  (esperado: 1)")

        cur.execute(
            """
            SELECT t.nombre_canonico, jt.requirement_type, jt.confidence
            FROM job_technology jt
            JOIN technology t ON t.technology_id = jt.technology_id
            WHERE jt.job_id = %s
            ORDER BY t.nombre_canonico
            """,
            (r.job_id,),
        )
        print("  tecnologías guardadas:")
        for nombre, tipo, conf in cur.fetchall():
            print(f"     - {nombre:<14} {tipo:<10} confidence={conf}")
finally:
    conn.close()

print()
print("=" * 66)
print("3) ROLLBACK (una fuente inválida debe abortar TODO)")
print("=" * 66)

conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM job")
        antes = cur.fetchone()[0]
finally:
    conn.close()

try:
    insert_job_with_technologies(
        extraction=extraction,
        source_name="PortalInventado",   # no existe -> SourceDesconocida
    )
    print("  NO lanzó error  <-- FALLA")
except Exception as exc:
    print(f"  Lanzó {type(exc).__name__} (correcto)")

conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM job")
        despues = cur.fetchone()[0]
finally:
    conn.close()

print(f"  jobs antes={antes}  despues={despues}")
print(f"  ¿No quedó job a medias? -> {'SI' if antes == despues else 'NO <-- FALLA'}")
print()
print(f"Para limpiar la prueba, borra el job_id={r.job_id} (ver instrucciones).")
