"""
Se usa un HTML de ejemplo guardado en disco en vez de traer una página real (asi la prueba
se puede hacer en cualquier momento sin depender de internet ni de que la página exista todavía).
"""

from pathlib import Path

from app.cleaner import clean_html

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_job.html"


def _load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_clean_html_incluye_contenido_relevante():
    html = _load_fixture()
    result = clean_html(html)

    # El texto de la oferta (dentro de <main>) SÍ debe estar presente.
    assert "Practicante de Eficiencia" in result
    assert "Power BI" in result
    assert "eficiencia operativa" in result


def test_clean_html_excluye_ruido():
    html = _load_fixture()
    result = clean_html(html)

    # El menú de navegación, el banner de cookies y el footer NO deben aparecer -- eso es justo lo que decompose() elimina.
    assert "Inicio" not in result
    assert "Aceptar" not in result
    assert "Todos los derechos reservados" not in result
    assert "analytics tracking" not in result


def test_clean_html_usa_contenido_semantico_cuando_existe():
    # Este fixture SÍ tiene <main>, así que clean_html debería usar ese camino (Paso 2a)
    html = _load_fixture()
    result = clean_html(html)

    assert len(result) >= 200 


def test_clean_html_sin_main_cae_a_heuristica():
    # Paso 2b (bloque <div> más largo) y aun así rescatar el
    # contenido relevante.
    html = """
    <html><body>
      <div class="menu">Inicio Empleos Contacto</div>
      <div class="contenido">
        Buscamos Analista de Datos con experiencia en SQL y Python
        para unirse a nuestro equipo de Business Intelligence.
        Se requiere manejo de Power BI y conocimientos de ETL.
      </div>
      <div class="footer">© 2026</div>
    </body></html>
    """
    result = clean_html(html)

    assert "Analista de Datos" in result
    assert "Inicio Empleos Contacto" not in result