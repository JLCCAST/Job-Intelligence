"""
Agentes de Job-Intelligence. Cada uno tiene UNA tarea fija y
Batuta (batuta.py) los encadena en un grafo de LangGraph:

    Lupa       -> lee la oferta y extrae requisitos (IA)
    Archivero  -> normaliza fuente/empresa/tecnologías y guarda en BD
    Balanza    -> calcula el Match Score (determinístico)

Y en el flujo de adaptar CV:

    Preguntón  -> te pregunta por lo que falta (pausa el flujo)
    Pluma      -> adapta el CV sin inventar nada (IA + validador)
    Notario    -> explica cada cambio de la IA; tú aceptas o rechazas (pausa el flujo)
    Imprenta   -> genera CV y Brechas en DOCX, solo con lo que aceptaste

Las llamadas a la IA pasan por app/llm.py (Gemini, con respaldo en Groq u Ollama).
"""
