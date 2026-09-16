"""
Prueba manual de los campos nuevos (company_name / source_name).

Correr desde la raíz del proyecto, con el venv activo:
    python probar_extraccion.py

Requiere GEMINI_API_KEY en el .env.
"""

from app.gemini import extract_job_info

CASOS = {
    "A) Empresa con nombre propio explícito": """
        Banco Pichincha se encuentra en búsqueda de un Practicante de
        Eficiencia. Requisitos: conocimientos avanzados de Python y SQL,
        deseable Power BI. Inglés intermedio.
    """,
    "B) Empresa anónima (esperado: no_especificado)": """
        Importante empresa del sector retail busca Analista de Datos.
        Se requiere manejo avanzado de SQL y Excel. Deseable Power BI.
    """,
    "C) LinkedIn como REQUISITO, no como fuente (esperado: no_especificado)": """
        Ferreyros busca Practicante de BI. Requisitos: SQL intermedio,
        Power BI. Recuerda mantener tu perfil de LinkedIn actualizado
        antes de postular.
    """,
    "D) Fuente real declarada (esperado: Computrabajo)": """
        Oferta publicada en Computrabajo. Empresa: Alicorp.
        Buscamos Analista Junior con conocimientos de Python y Power BI.
    """,
}

for titulo, texto in CASOS.items():
    print("=" * 70)
    print(titulo)
    print("=" * 70)
    resultado = extract_job_info(texto.strip())

    if not resultado.success:
        print("  ERROR:", resultado.error)
        print()
        continue

    d = resultado.data
    print(f"  company_name : {d.company_name!r}")
    print(f"  source_name  : {d.source_name!r}")
    print(f"  job_title    : {d.job_title!r}")
    print(f"  area         : {d.area}")
    print(f"  disponible   : {d.is_offer_available}")
    print(f"  tecnologías  : {[t.name for t in d.technologies]}")
    print()
