"""
Prueba del Match Score contra la Supabase REAL.

    python probar_score.py

NO llama a Gemini: usa los jobs que ya tienes registrados.

Qué hace:
  1. Muestra tu perfil cargado (user_skill).
  2. Recalcula el score de TODOS los jobs y muestra el desglose
     del primero, ítem por ítem, para que puedas verificar la
     aritmética a mano.
"""

from dotenv import load_dotenv

load_dotenv()

from app.repository import (
    get_connection,
    calcular_y_guardar_match_score,
    recalcular_todos_los_scores,
)

print("=" * 70)
print("TU PERFIL (user_skill)")
print("=" * 70)

conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT t.nombre_canonico, t.categoria, us.level
            FROM user_skill us
            JOIN technology t ON t.technology_id = us.technology_id
            ORDER BY t.categoria, t.nombre_canonico
            """
        )
        filas = cur.fetchall()
        for nombre, categoria, level in filas:
            print(f"  {categoria:<16} {nombre:<26} {level}")
        print(f"\n  Total: {len(filas)} habilidades")

        cur.execute("SELECT job_id, puesto FROM job ORDER BY job_id")
        jobs = cur.fetchall()
finally:
    conn.close()

if not jobs:
    print("\nNo hay jobs registrados todavía. Registra uno con /analyze-job.")
    raise SystemExit

print()
print("=" * 70)
print("RECÁLCULO DE TODOS LOS SCORES")
print("=" * 70)

for job_id, score in recalcular_todos_los_scores():
    puesto = next(p for i, p in jobs if i == job_id)
    texto = "sin datos" if score is None else f"{score:>6.2f}%"
    print(f"  job_id={job_id:<4} {texto}  {puesto}")

print()
print("=" * 70)
print(f"DESGLOSE DEL job_id={jobs[0][0]} (verifica la aritmética a mano)")
print("=" * 70)

r = calcular_y_guardar_match_score(jobs[0][0])

print(f"  {'tecnología':<24} {'tipo':<10} {'pide':<13} {'tengo':<13} {'peso':>5} {'créd':>5} {'aporte':>7}")
print("  " + "-" * 82)
for item in r.items:
    print(
        f"  {item.nombre:<24} {item.requirement_type:<10} "
        f"{str(item.nivel_pedido):<13} {str(item.nivel_usuario):<13} "
        f"{item.peso:>5.1f} {item.credito:>5.1f} {item.aporte:>7.2f}"
    )

peso_total = sum(i.peso for i in r.items)
aporte_total = sum(i.aporte for i in r.items)
print("  " + "-" * 82)
print(f"  {'TOTAL':<24} {'':<10} {'':<13} {'':<13} {peso_total:>5.1f} {'':>5} {aporte_total:>7.2f}")
print()
print(f"  Score = {aporte_total:.2f} / {peso_total:.1f} * 100 = {r.score}%")
print(f"  Cumple inglés        : {r.cumple_ingles}")
print(f"  No tienes            : {r.faltantes or 'nada'}")
print(f"  Obligatorias cortas  : {r.requisitos_bajo_nivel or 'ninguna'}")
if r.requisitos_bajo_nivel:
    print("     ^ las tienes, pero por debajo del nivel que piden.")
    print("       El score las suaviza (crédito 0.7); esta línea las deja visibles.")
