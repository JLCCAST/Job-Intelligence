"""
Adapta tu CV a una oferta ya registrada, desde la consola (hasta
que exista la app de Streamlit). Usa Supabase y Gemini REALES.

    python -m scripts.adaptar_cv            -> lista tus ofertas
    python -m scripts.adaptar_cv <job_id>   -> adapta el CV a esa oferta

Si el Preguntón tiene preguntas, te las hace aquí mismo. Los DOCX
quedan en la carpeta salidas/.
"""

import sys

from app.repository import get_connection
from app.services import iniciar_adaptacion_cv, responder_preguntas

NIVELES = {"1": "basico", "2": "intermedio", "3": "avanzado"}


def listar_ofertas() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT j.job_id, j.puesto, c.nombre, j.match_score
                FROM job j JOIN company c ON c.company_id = j.company_id
                ORDER BY j.job_id DESC
                """
            )
            filas = cur.fetchall()
    finally:
        conn.close()

    print(f"{'job_id':>6}  {'score':>6}  puesto — empresa")
    for job_id, puesto, empresa, score in filas:
        score_txt = f"{score:.1f}" if score is not None else "—"
        print(f"{job_id:>6}  {score_txt:>6}  {puesto} — {empresa}")


def preguntar_en_consola(preguntas: list[dict]) -> list[dict]:
    respuestas = []
    for p in preguntas:
        print("\n" + p["texto"])
        la_tengo = input("  ¿Lo tienes? (s/n): ").strip().lower().startswith("s")
        respuesta = {"tecnologia": p["tecnologia"], "la_tengo": la_tengo}
        if la_tengo:
            nivel = input("  Nivel (1=básico, 2=intermedio, 3=avanzado): ").strip()
            respuesta["nivel"] = NIVELES.get(nivel)
            respuesta["donde"] = input("  ¿Dónde lo usaste? (proyecto, trabajo o curso): ").strip() or None
            respuesta["detalle"] = input("  ¿Qué hiciste con eso? (una línea): ").strip() or None
        respuestas.append(respuesta)
    return respuestas


def main() -> None:
    if len(sys.argv) < 2:
        listar_ofertas()
        print("\nUsa: python -m scripts.adaptar_cv <job_id>")
        return

    resultado = iniciar_adaptacion_cv(int(sys.argv[1]))
    if resultado["esperando_respuestas"]:
        print(f"El Preguntón tiene {len(resultado['preguntas'])} pregunta(s):")
        respuestas = preguntar_en_consola(resultado["preguntas"])
        resultado = responder_preguntas(resultado["thread_id"], respuestas)

    print("\nListo:")
    print(f"  CV:       {resultado['ruta_cv']}")
    print(f"  Brechas:  {resultado['ruta_brechas']}")
    if not resultado["usa_texto_de_pluma"]:
        print("  Aviso: el CV usa tus bullets originales. Motivos:")
        for aviso in resultado["avisos"]:
            print(f"    - {aviso}")


if __name__ == "__main__":
    main()
