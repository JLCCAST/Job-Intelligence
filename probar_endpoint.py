"""
Prueba del endpoint completo contra Gemini y Supabase REALES.

Levanta el servidor en otra terminal:
    uvicorn app.main:app --reload

y luego, desde la raíz del proyecto:
    python probar_endpoint.py

Valida el flujo end-to-end y, sobre todo, que reenviar la MISMA
URL no cree un job duplicado.
"""

import json
import requests

BASE = "http://127.0.0.1:8000/analyze-job"

TEXTO = """
Alicorp se encuentra en búsqueda de un Practicante de Business Intelligence.
Requisitos: conocimientos avanzados de SQL y Power BI. Deseable experiencia
con Python y Power Query. Inglés intermedio. El practicante apoyará en la
automatización de reportes de gestión y en el modelado de datos del área.
"""


def mostrar(titulo, payload):
    print("=" * 66)
    print(titulo)
    print("=" * 66)
    r = requests.post(BASE, json=payload, timeout=120)
    d = r.json()

    print(f"  HTTP                 : {r.status_code}")
    print(f"  extraction_status    : {d.get('extraction_status')}")
    print(f"  registration_status  : {d.get('registration_status')}")
    print(f"  job_id               : {d.get('job_id')}")
    if d.get("error_detail"):
        print(f"  error_detail         : {d['error_detail']}")
    if d.get("extraction"):
        e = d["extraction"]
        print(f"  empresa detectada    : {e['company_name']}")
        print(f"  puesto               : {e['job_title']}")
        print(f"  tecnologías          : {[t['name'] for t in e['technologies']]}")
    if d.get("tecnologias_para_revisar"):
        print(f"  para revisar         : {d['tecnologias_para_revisar']}")
    print()
    return d


# 1. Texto pegado (Opción B) -- debería guardar.
d1 = mostrar("1) TEXTO PEGADO", {"text": TEXTO.strip()})

# 2. URL real y simple. Cambia esta URL por una oferta de verdad si quieres.
URL = "https://empresa-de-prueba-inexistente.com/oferta"
d2 = mostrar("2) URL (probablemente falle el fetch, es esperado)", {"url": URL})

# 3. La MISMA URL otra vez -- si la 2 guardó, esta debe decir 'duplicate'.
d3 = mostrar("3) MISMA URL DE NUEVO (esperado: duplicate)", {"url": URL})

print("=" * 66)
print("RESUMEN")
print("=" * 66)
print(f"  Texto pegado guardó job_id={d1.get('job_id')}")
if d2.get("registration_status") == "saved":
    ok = d3.get("registration_status") == "duplicate" and d3.get("job_id") == d2.get("job_id")
    print(f"  ¿Detectó el duplicado? -> {'SI' if ok else 'NO <-- FALLA'}")
else:
    print("  (La URL no llegó a guardarse, así que el test de duplicado no aplica.)")
