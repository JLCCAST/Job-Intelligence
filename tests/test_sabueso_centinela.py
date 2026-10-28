"""
Tests de Sabueso (fuente Get on Board + filtro + tope) y Centinela
(resumen y notificación). Sin red, sin Gemini y sin Supabase.
"""

from app.agents import centinela, lupa, sabueso
from app.fuentes import OfertaEncontrada, getonbrd

ITEM_GETONBRD = {
    "id": "data-analyst-empresa-lima",
    "type": "job",
    "attributes": {
        "title": "Data Analyst",
        "description_headline": "Requisitos",
        "description": "<ul><li>SQL avanzado</li><li>Power BI</li></ul>",
        "functions_headline": "Funciones",
        "functions": "<p>Construir dashboards.</p>",
        "desirable_headline": "Deseable",
        "desirable": None,
        "benefits_headline": "Beneficios",
        "benefits": "<p>Seguro.</p>",
        "remote": False,
        "remote_modality": "hybrid",
        "countries": ["Peru"],
        "min_salary": 1200,
        "max_salary": 1800,
        "company": {"data": {"attributes": {"name": "Empresa Ficticia"}}},
    },
    "links": {"public_url": "https://www.getonbrd.com/jobs/data-analyst-empresa-lima"},
}


# --------- Fuente Get on Board ---------

def test_convertir_arma_texto_plano_con_todas_las_secciones():
    oferta = getonbrd.convertir(ITEM_GETONBRD)
    assert oferta.empresa == "Empresa Ficticia"
    assert oferta.paises == ["Peru"]
    assert "SQL avanzado" in oferta.texto and "<li>" not in oferta.texto
    assert "Construir dashboards." in oferta.texto
    assert "Salario (USD/mes): 1200 - 1800" in oferta.texto
    assert "Publicado en Get on Board." in oferta.texto


# --------- Filtro ---------

def _oferta(url, paises=("Chile",), remoto=False):
    return OfertaEncontrada(fuente="Get on Board", url=url, titulo=url, empresa="X",
                            paises=list(paises), remoto=remoto, texto="texto")


def test_filtro_por_pais_y_remoto():
    assert sabueso.pasa_filtro(_oferta("a", ["Peru"]), ["Peru"], incluir_remoto=False)
    assert not sabueso.pasa_filtro(_oferta("b", ["Chile"]), ["Peru"], incluir_remoto=False)
    assert sabueso.pasa_filtro(_oferta("c", ["Remote"], remoto=True), ["Peru"], incluir_remoto=True)
    assert not sabueso.pasa_filtro(_oferta("d", ["Remote"], remoto=True), ["Peru"], incluir_remoto=False)


# --------- Corrida completa ---------

def test_ejecutar_deduplica_filtra_y_respeta_el_tope(monkeypatch):
    ofertas = [
        _oferta("https://x/1", ["Peru"]),
        _oferta("https://x/2", ["Peru"]),
        _oferta("https://x/3", ["Peru"]),
        _oferta("https://x/ya", ["Peru"]),
        _oferta("https://x/chile", ["Chile"]),
    ]
    # Dos búsquedas devuelven lo mismo: no debe duplicar.
    monkeypatch.setitem(sabueso.FUENTES, "getonbrd", lambda consulta: ofertas)
    monkeypatch.setattr(sabueso, "buscar_job_por_url", lambda url: 9 if url.endswith("/ya") else None)
    analizadas = []

    def fake_analizar(url, text, origen=None):
        analizadas.append(url)
        return {"registration_status": "saved", "job_id": len(analizadas), "match_score": 80.0}

    monkeypatch.setattr(sabueso.batuta, "analizar", fake_analizar)

    config = {"consultas": ["data", "bi"], "paises": ["Peru"], "incluir_remoto": True, "max_nuevas_por_corrida": 2}
    r = sabueso.ejecutar(config)

    assert r.encontradas == 5
    assert r.fuera_de_filtro == 1
    assert r.ya_registradas == 1
    assert analizadas == ["https://x/1", "https://x/2"]
    assert r.pendientes_por_tope == 1
    assert len(r.registradas) == 2


def test_lupa_usa_el_texto_de_la_api_sin_descargar_la_url(monkeypatch):
    monkeypatch.setattr(lupa, "buscar_job_por_url", lambda url: None)
    monkeypatch.setattr(lupa, "fetch_html", lambda url: (_ for _ in ()).throw(AssertionError("no debía descargar")))
    estado = lupa.leer_oferta({"url": "https://www.getonbrd.com/jobs/x", "text": "Oferta " * 50, "origen": "api"})
    assert estado["source"] == "api"
    assert estado["url"] == "https://www.getonbrd.com/jobs/x"


# --------- Centinela ---------

RESUMEN = {
    "fecha": "2026-10-23",
    "nuevas": [
        {"job_id": 1, "puesto": "Data Analyst", "empresa": "Empresa Ficticia", "fuente": "Get on Board",
         "match_score": 88.0, "url": "https://x/1"},
    ],
    "recordatorios": [{"job_id": 2, "puesto": "Practicante BI", "empresa": "Alicorp", "dias": 9}],
    "dias_sin_respuesta": 7,
}


def test_resumen_markdown_incluye_nuevas_y_seguimiento():
    sabueso_dict = {"encontradas": 5, "fuera_de_filtro": 1, "ya_registradas": 1, "registradas": [{}],
                    "descartadas": ["X: 503"], "pendientes_por_tope": 2, "errores": []}
    texto = centinela.resumen_markdown(RESUMEN, sabueso_dict)
    assert "**88%** · Data Analyst · Empresa Ficticia" in texto
    assert "Practicante BI · Alicorp: 9 días sin respuesta" in texto
    assert "Quedaron 2 para mañana" in texto
    assert "No se pudieron registrar 1" in texto


def test_guardar_resumen_y_texto_de_notificacion(tmp_path):
    ruta = centinela.guardar_resumen("# hola\n", "2026-10-23", carpeta=tmp_path)
    assert ruta.name == "resumen_2026-10-23.md"
    titulo, cuerpo = centinela.texto_notificacion(RESUMEN)
    assert titulo == "1 oferta(s) nueva(s)"
    assert "Data Analyst (88%)" in cuerpo and "1 postulación(es)" in cuerpo


def test_filtro_de_titulo_por_palabras_completas_y_sin_tildes():
    palabras = ["data", "bi", "analítica"]
    assert sabueso.titulo_relevante("Data Analyst", palabras)
    assert sabueso.titulo_relevante("Desarrollador BI Microsoft", palabras)
    assert sabueso.titulo_relevante("Jefe de Analitica", palabras)
    assert not sabueso.titulo_relevante("Analista Funcional ISU DM", palabras)
    assert not sabueso.titulo_relevante("Full-Stack Bilingüe", palabras)


def test_filtro_excluye_senior_y_lead():
    palabras, excluidas = ["data"], ["senior", "lead", "semi senior"]
    assert not sabueso.titulo_relevante("Senior Data Engineer", palabras, excluidas)
    assert not sabueso.titulo_relevante("Lead Data Scientist", palabras, excluidas)
    assert sabueso.titulo_relevante("Data Engineer Jr", palabras, excluidas)


def test_gemini_reintenta_solo_errores_temporales(monkeypatch):
    from app import gemini

    llamadas = []

    class Modelos:
        def generate_content(self, **kwargs):
            llamadas.append(1)
            if len(llamadas) < 3:
                raise RuntimeError("503 UNAVAILABLE")
            return "ok"

    class Cliente:
        models = Modelos()

    monkeypatch.setattr(gemini, "_get_client", lambda: Cliente())
    monkeypatch.setattr(gemini.time, "sleep", lambda s: None)
    assert gemini._generar(model="x") == "ok"
    assert len(llamadas) == 3

    llamadas.clear()
    Modelos.generate_content = lambda self, **k: (llamadas.append(1), (_ for _ in ()).throw(ValueError("400 bad")))[1]
    try:
        gemini._generar(model="x")
    except ValueError:
        pass
    assert len(llamadas) == 1  # un error que no es temporal no se reintenta


def test_sabueso_se_detiene_si_se_agota_la_cuota_diaria(monkeypatch):
    ofertas = [_oferta(f"https://x/{i}", ["Peru"]) for i in range(4)]
    monkeypatch.setitem(sabueso.FUENTES, "getonbrd", lambda consulta: ofertas)
    monkeypatch.setattr(sabueso, "buscar_job_por_url", lambda url: None)
    llamadas = []

    def fake_analizar(url, text, origen=None):
        llamadas.append(url)
        if len(llamadas) == 1:
            return {"registration_status": "saved", "job_id": 1, "match_score": 50.0}
        return {"registration_status": "not_attempted",
                "error_detail": "429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier"}

    monkeypatch.setattr(sabueso.batuta, "analizar", fake_analizar)
    r = sabueso.ejecutar({"consultas": ["x"], "paises": ["Peru"], "max_nuevas_por_corrida": 10})
    assert len(llamadas) == 2                 # no siguió gastando
    assert r.pendientes_por_tope == 3
    assert "cuota diaria" in r.errores[0]


def test_cada_agente_tiene_su_modelo_y_el_env_manda(monkeypatch):
    from app import gemini

    for var in ("GEMINI_MODELO", "GEMINI_MODELO_LUPA", "GEMINI_MODELO_PLUMA"):
        monkeypatch.delenv(var, raising=False)
    assert gemini.modelo_para("lupa") != gemini.modelo_para("pluma")

    monkeypatch.setenv("GEMINI_MODELO", "modelo-global")
    assert gemini.modelo_para("pluma") == "modelo-global"

    monkeypatch.setenv("GEMINI_MODELO_PLUMA", "modelo-pluma")
    assert gemini.modelo_para("pluma") == "modelo-pluma"
    assert gemini.modelo_para("lupa") == "modelo-global"

    monkeypatch.setenv("GEMINI_MODELO_LUPA", "lite-a, lite-b")
    assert gemini.modelos_para("lupa") == ["lite-a", "lite-b"]


def test_si_un_modelo_agota_su_cuota_diaria_pasa_al_siguiente(monkeypatch):
    from app import gemini

    monkeypatch.setenv("GEMINI_MODELO_LUPA", "lite-a,lite-b")
    monkeypatch.setattr(gemini, "_agotados_hoy", set())
    usados = []

    def fake_generar(model, **kwargs):
        usados.append(model)
        if model == "lite-a":
            raise RuntimeError("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        return "ok"

    monkeypatch.setattr(gemini, "_generar", fake_generar)
    assert gemini._generar_para("lupa", contents="x") == ("ok", "lite-b")
    # La segunda vez ya no pierde una petición con el modelo agotado.
    assert gemini._generar_para("lupa", contents="x") == ("ok", "lite-b")
    assert usados == ["lite-a", "lite-b", "lite-b"]


def test_si_todos_agotan_la_cuota_el_error_sigue_siendo_de_cuota_diaria(monkeypatch):
    from app import gemini

    monkeypatch.setenv("GEMINI_MODELO_LUPA", "lite-a,lite-b")
    monkeypatch.setattr(gemini, "_agotados_hoy", set())

    def siempre_agotado(model, **kwargs):
        raise RuntimeError("429 RESOURCE_EXHAUSTED PerDay")

    monkeypatch.setattr(gemini, "_generar", siempre_agotado)
    try:
        gemini._generar_para("lupa", contents="x")
    except RuntimeError as exc:
        assert gemini.es_cuota_diaria_agotada(exc)   # Sabueso se detiene con esto
        assert "lite-b" in str(exc)
    else:
        raise AssertionError("debía fallar")
