"""
cargar_mi_perfil.py

Carga tu perfil de habilidades en la tabla `user_skill`.
Sin esto, el Match Score de toda oferta da 0%.

    python cargar_mi_perfil.py

Niveles válidos: "basico", "intermedio", "avanzado".

El script es idempotente: puedes correrlo las veces que quieras.
Si una habilidad ya existe, se ACTUALIZA (no se duplica), así que
la forma de corregir un nivel es editar acá y volver a correrlo.

Categorías válidas (enum cerrado, igual que en schemas.py):
    Programming, Database, Cloud, BI_Tool, Automation_Tool,
    Framework, Methodology, Soft_Skill, Other
"""

from dotenv import load_dotenv

load_dotenv()

from app.repository import cargar_perfil

MI_PERFIL = [
    # --- Lenguajes ---
    {"nombre": "Python", "categoria": "Programming", "level": "intermedio",
     "evidencia": "Microservicio de este proyecto (FastAPI + scraping + Gemini)"},
    {"nombre": "Java", "categoria": "Programming", "level": "basico",
     "evidencia": "Cursos de la carrera"},
    {"nombre": "JavaScript", "categoria": "Programming", "level": "intermedio",
     "evidencia": "Proyectos de la carrera y portafolio"},
    {"nombre": "TypeScript", "categoria": "Programming", "level": "basico",
        "evidencia": "Proyectos de la carrera y portafolio"},

    # --- Bases de datos ---
    {"nombre": "SQL", "categoria": "Database", "level": "avanzado",
     "evidencia": "Modelado y consultas en proyectos de BI"},
    {"nombre": "SQL Server", "categoria": "Database", "level": "intermedio",
     "evidencia": "Proyectos de Data Warehouse"},
    {"nombre": "PostgreSQL", "categoria": "Database", "level": "intermedio",
     "evidencia": "Modelado y consultas sobre Supabase en este proyecto"},

    # --- BI ---
    {"nombre": "Power BI", "categoria": "BI_Tool", "level": "intermedio",
     "evidencia": "Reportes y modelado en proyectos de la carrera"},
    {"nombre": "Power Query", "categoria": "BI_Tool", "level": "intermedio",
     "evidencia": "Transformaciones dentro de Power BI"},
    {"nombre": "Pentaho", "categoria": "BI_Tool", "level": "basico",
     "evidencia": "Flujos de ETL en curso de BI"},

    # --- Data engineering / metodologías ---
    {"nombre": "ETL", "categoria": "Methodology", "level": "intermedio",
     "evidencia": "Pipelines en Pentaho y Python"},
    {"nombre": "Data Warehouse", "categoria": "Methodology", "level": "intermedio",
     "evidencia": "Diseño de DW en proyectos de la carrera"},
    {"nombre": "Modelado dimensional", "categoria": "Methodology", "level": "intermedio",
     "evidencia": "Star Schema en proyectos de DW"},
    {"nombre": "Star Schema", "categoria": "Methodology", "level": "intermedio",
     "evidencia": "Modelado de hechos y dimensiones"},
    {"nombre": "Arquitectura Medallion", "categoria": "Methodology", "level": "basico",
     "evidencia": "Bronze/Silver/Gold en proyecto de datos"},
    {"nombre": "Calidad de datos", "categoria": "Methodology", "level": "basico",
     "evidencia": "Validaciones y limpieza en pipelines"},
    {"nombre": "Machine Learning", "categoria": "Methodology", "level": "basico",
     "evidencia": "Cursos y proyectos con PyTorch"},
    {"nombre": "APIs REST", "categoria": "Methodology", "level": "intermedio",
     "evidencia": "Consumo de Gemini y diseño del endpoint propio"},

    # --- Frameworks ---
    {"nombre": "PySpark", "categoria": "Framework", "level": "basico",
     "evidencia": "Procesamiento distribuido en proyecto de datos"},
    {"nombre": "PyTorch", "categoria": "Framework", "level": "basico",
     "evidencia": "Modelos de ML en cursos"},
    {"nombre": "FastAPI", "categoria": "Framework", "level": "basico",
     "evidencia": "Endpoint /analyze-job de este proyecto"},

    # --- Cloud / infra ---
    {"nombre": "Azure", "categoria": "Cloud", "level": "basico",
     "evidencia": "Pruebas con cuenta de estudiante"},
    {"nombre": "Docker", "categoria": "Other", "level": "basico",
     "evidencia": "Contenedores en cursos"},
    {"nombre": "Kubernetes", "categoria": "Other", "level": "basico",
     "evidencia": "Orquestación en cursos"},
    {"nombre": "Git", "categoria": "Other", "level": "intermedio",
     "evidencia": "Control de versiones de este proyecto"},

    # --- Soft skills ---
    {"nombre": "Trabajo en equipo", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Proyectos grupales de la carrera"},
    {"nombre": "Comunicación", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Exposiciones y documentación de proyectos"},
    {"nombre": "Proactividad", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Proyectos propios de portafolio fuera de los cursos"},
    {"nombre": "Pensamiento analítico", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Análisis y modelado de datos en proyectos de BI"},
    {"nombre": "Resolución de problemas", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Diagnóstico de bugs reales documentados en este proyecto"},
    {"nombre": "Adaptabilidad", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Cambio de Azure SQL a Supabase al toparse con restricciones"},
    {"nombre": "Atención al detalle", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Suite de pruebas y validación de datos del pipeline"},
    {"nombre": "Aprendizaje continuo", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "FastAPI, scraping e integración de LLM aprendidos para este proyecto"},
    {"nombre": "Organización", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Proyecto avanzado por fases, con commits y documentación"},
    {"nombre": "Autonomía", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Proyecto de portafolio llevado solo de punta a punta"},

    {"nombre": "Inglés", "categoria": "Soft_Skill", "level": "intermedio",
     "evidencia": "Lectura de documentación técnica"},
]

if __name__ == "__main__":
    total = cargar_perfil(MI_PERFIL)
    print(f"Se cargaron/actualizaron {total} habilidades en user_skill.")
    print("Revisa los niveles y vuelve a correr el script si corriges alguno.")