"""
Tests del mapeo determinístico dominio -> source.

No tocan red ni BD: es lógica pura, así que son instantáneos.
"""

import pytest

from app.source_resolver import resolver_source_desde_url, resolver_source


@pytest.mark.parametrize(
    "url, esperado",
    [
        # Portales conocidos, en sus distintas formas de hostname.
        ("https://www.linkedin.com/jobs/view/123", "LinkedIn"),
        ("https://pe.linkedin.com/jobs/view/123", "LinkedIn"),
        ("https://linkedin.com/jobs/view/123", "LinkedIn"),
        ("https://pe.indeed.com/viewjob?jk=abc", "Indeed"),
        ("https://pe.computrabajo.com/trabajo-de-analista", "Computrabajo"),
        ("https://www.computrabajo.com.pe/oferta/456", "Computrabajo"),
        ("https://www.bumeran.com.pe/empleos/analista.html", "Bumeran"),
        # Con puerto explícito y en mayúsculas: debe normalizar igual.
        ("https://WWW.LinkedIn.COM:443/jobs/1", "LinkedIn"),
    ],
)
def test_portales_conocidos(url, esperado):
    assert resolver_source_desde_url(url) == esperado


@pytest.mark.parametrize(
    "url",
    [
        # Portal propio de la empresa (caso Ferreyros / SuccessFactors).
        "https://careers.ferreyros.com.pe/job/12345",
        "https://jobs.sap.com/vacante/99",
        "https://empresa-cualquiera.com/trabaja-con-nosotros",
    ],
)
def test_dominio_desconocido_cae_a_career_page(url):
    assert resolver_source_desde_url(url) == "Career Page"


def test_no_confunde_dominio_que_solo_contiene_el_nombre():
    # Sin el punto en el sufijo, esto daría falso positivo -> Indeed.
    assert resolver_source_desde_url("https://fakeindeed.com/job/1") == "Career Page"
    assert resolver_source_desde_url("https://milinkedin.com/x") == "Career Page"


def test_url_basura_no_lanza_excepcion():
    # No debe reventar el pipeline entero por una URL rara.
    assert resolver_source_desde_url("no-es-una-url") == "Career Page"
    assert resolver_source_desde_url("") == "Career Page"


# --------- Regla de precedencia completa ---------

def test_url_manda_sobre_lo_que_dijo_gemini():
    # Gemini dice Bumeran, pero el dominio dice LinkedIn: gana el dominio.
    resultado = resolver_source(
        url="https://www.linkedin.com/jobs/view/1",
        source_name_gemini="Bumeran",
    )
    assert resultado == "LinkedIn"


def test_sin_url_se_usa_lo_de_gemini():
    resultado = resolver_source(url=None, source_name_gemini="Computrabajo")
    assert resultado == "Computrabajo"


def test_sin_url_y_gemini_no_especificado_cae_a_otro():
    resultado = resolver_source(url=None, source_name_gemini="no_especificado")
    assert resultado == "Otro"


def test_sin_url_y_sin_dato_de_gemini_cae_a_otro():
    assert resolver_source(url=None, source_name_gemini=None) == "Otro"


def test_canonicalizar_unifica_las_urls_de_get_on_board():
    from app.source_resolver import canonicalizar_url

    api = "https://www.getonbrd.com/jobs/data-analyst-colectivo23-lima"
    navegador = "https://www.getonbrd.com/empleos/data-science-analytics/data-analyst-colectivo23-lima"
    assert canonicalizar_url(navegador) == api
    assert canonicalizar_url(api) == api


def test_canonicalizar_quita_parametros_de_seguimiento_y_barra_final():
    from app.source_resolver import canonicalizar_url

    url = "https://www.linkedin.com/jobs/view/123/?trk=public&utm_source=x&currentJobId=123"
    assert canonicalizar_url(url) == "https://www.linkedin.com/jobs/view/123?currentJobId=123"
    assert canonicalizar_url(None) is None


def test_computrabajo_conserva_el_id_de_la_oferta_en_listas_de_resultados():
    from app.source_resolver import canonicalizar_url

    a = "https://pe.computrabajo.com/trabajo-de-practicante-analitica#7539C28879C5B12A61373E686DCF3405"
    b = "https://pe.computrabajo.com/trabajo-de-practicante-analitica#11111111111111111111111111111111"
    assert canonicalizar_url(a) == a
    assert canonicalizar_url(a) != canonicalizar_url(b)
    assert canonicalizar_url("https://www.linkedin.com/jobs/view/1#seccion") == "https://www.linkedin.com/jobs/view/1"
