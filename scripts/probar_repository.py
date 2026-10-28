"""
Prueba de repository.py contra la Supabase REAL.

Correr desde la raíz del proyecto, con el venv activo:
    python -m scripts.probar_repository

Requiere SUPABASE_DB_URL en el .env.

Qué valida:
  - Que el SQL corra sin errores contra el motor real.
  - Que la 2da llamada con el MISMO nombre NO cree una fila nueva
    (es decir, que company_alias está haciendo su trabajo).
  - Que una variación de mayúsculas caiga en la misma empresa.
  - Que las 6 fuentes del catálogo se resuelvan, y que una
    inventada lance SourceDesconocida en vez de crearla.
"""

from dotenv import load_dotenv

load_dotenv()

from app.repository import (
    resolver_company_id,
    resolver_source_id,
    SourceDesconocida,
    EMPRESA_CENTINELA,
)

print("=" * 66)
print("COMPANY")
print("=" * 66)

id_1 = resolver_company_id("Banco Pichincha")
print(f"  1ra vez 'Banco Pichincha' -> company_id={id_1}")

id_2 = resolver_company_id("Banco Pichincha")
print(f"  2da vez 'Banco Pichincha' -> company_id={id_2}")
print(f"  ¿Mismo id (no duplicó)?   -> {'SI' if id_1 == id_2 else 'NO <-- FALLA'}")
print()

id_3 = resolver_company_id("BANCO PICHINCHA")
print(f"  'BANCO PICHINCHA'         -> company_id={id_3}")
print(f"  ¿Cayó en la misma fila?   -> {'SI' if id_3 == id_1 else 'NO <-- FALLA'}")
print()

id_anon_1 = resolver_company_id("no_especificado")
id_anon_2 = resolver_company_id(None)
print(f"  'no_especificado'         -> company_id={id_anon_1}")
print(f"  None                      -> company_id={id_anon_2}")
print(f"  ¿Ambas al centinela {EMPRESA_CENTINELA!r}? -> "
      f"{'SI' if id_anon_1 == id_anon_2 else 'NO <-- FALLA'}")
print()

print("=" * 66)
print("SOURCE")
print("=" * 66)

for nombre in ["LinkedIn", "Indeed", "Computrabajo", "Bumeran", "Career Page", "Otro"]:
    print(f"  {nombre:<14} -> source_id={resolver_source_id(nombre)}")

print()
try:
    resolver_source_id("PortalInventado")
    print("  'PortalInventado' -> NO lanzó error  <-- FALLA")
except SourceDesconocida as exc:
    print(f"  'PortalInventado' -> SourceDesconocida (correcto)")
    print(f"     {exc}")
