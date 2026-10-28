"""
sabueso.py -- agente Sabueso

Tarea fija: buscar ofertas nuevas en las fuentes permitidas
(app/fuentes) y pasar cada una por el flujo de Batuta (Lupa ->
Archivero -> Balanza). Lo que registra queda en estado "Registrada":
esa es tu bandeja de entrada en la app.

Sin LLM propio: filtra y deduplica en Python. Gemini solo se usa
dentro de Lupa, y con un tope por corrida para cuidar la cuota.
"""

import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import requests
import yaml

from app.agents import batuta
from app.cv.cargador import RAIZ
from app.fuentes import OfertaEncontrada, getonbrd
from app.gemini import es_cuota_diaria_agotada
from app.repository import buscar_job_por_url
from app.source_resolver import canonicalizar_url

RUTA_CONFIG = RAIZ / "config" / "sabueso.yaml"
FUENTES = {"getonbrd": getonbrd.buscar}


@dataclass
class ResultadoSabueso:
    encontradas: int = 0           # todo lo que devolvieron las fuentes
    fuera_de_filtro: int = 0       # país/modalidad que no te interesa
    ya_registradas: int = 0        # duplicadas por URL
    registradas: list[dict] = field(default_factory=list)   # job_id, puesto, empresa, score
    descartadas: list[str] = field(default_factory=list)    # cerradas o con error
    pendientes_por_tope: int = 0   # quedaron para la siguiente corrida
    errores: list[str] = field(default_factory=list)


def cargar_config(ruta: Path = None) -> dict:
    with open(ruta or RUTA_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def _contiene_alguna(titulo: str, palabras: list[str]) -> bool:
    """¿Alguna palabra aparece como palabra completa? ("bi" no calza con "bilingüe")."""
    limpio = _sin_tildes(titulo)
    return any(re.search(rf"(?<!\w){re.escape(_sin_tildes(p))}(?!\w)", limpio) for p in palabras)


def titulo_relevante(titulo: str, palabras: list[str], excluidas: list[str] = ()) -> bool:
    if excluidas and _contiene_alguna(titulo, list(excluidas)):
        return False
    return not palabras or _contiene_alguna(titulo, palabras)


def pasa_filtro(
    oferta: OfertaEncontrada,
    paises: list[str],
    incluir_remoto: bool,
    palabras_titulo: list[str] = (),
    excluidas_titulo: list[str] = (),
) -> bool:
    if not titulo_relevante(oferta.titulo, list(palabras_titulo), list(excluidas_titulo)):
        return False
    if incluir_remoto and oferta.remoto:
        return True
    buscados = {p.lower() for p in paises}
    return any(p.lower() in buscados for p in oferta.paises)


def buscar_candidatas(config: dict, resultado: ResultadoSabueso) -> list[OfertaEncontrada]:
    """Junta las ofertas de todas las búsquedas, sin repetir URL."""
    vistas: dict[str, OfertaEncontrada] = {}
    for nombre in config.get("fuentes", list(FUENTES)):
        for consulta in config["consultas"]:
            try:
                ofertas = FUENTES[nombre](consulta)
            except requests.RequestException as exc:
                resultado.errores.append(f"{nombre} / '{consulta}': {exc}")
                continue
            for oferta in ofertas:
                vistas.setdefault(oferta.url, oferta)

    resultado.encontradas = len(vistas)
    candidatas = []
    for oferta in vistas.values():
        if not pasa_filtro(
            oferta, config.get("paises", []), config.get("incluir_remoto", False),
            config.get("palabras_clave_titulo", []), config.get("palabras_excluidas_titulo", []),
        ):
            resultado.fuera_de_filtro += 1
        elif buscar_job_por_url(canonicalizar_url(oferta.url)) is not None:
            resultado.ya_registradas += 1
        else:
            candidatas.append(oferta)
    return candidatas


def ejecutar(config: dict = None) -> ResultadoSabueso:
    config = config or cargar_config()
    resultado = ResultadoSabueso()
    candidatas = buscar_candidatas(config, resultado)

    tope = config.get("max_nuevas_por_corrida", 10)
    resultado.pendientes_por_tope = max(0, len(candidatas) - tope)

    pausa = config.get("pausa_entre_ofertas_segundos", 0)
    lote = candidatas[:tope]
    for i, oferta in enumerate(lote):
        if i and pausa:
            time.sleep(pausa)  # no saturar a Gemini con una ráfaga
        estado = batuta.analizar(url=oferta.url, text=oferta.texto, origen="api")
        if estado.get("registration_status") == "saved":
            resultado.registradas.append({
                "job_id": estado["job_id"],
                "puesto": oferta.titulo,
                "empresa": oferta.empresa,
                "match_score": estado.get("match_score"),
                "url": oferta.url,
            })
        elif es_cuota_diaria_agotada(estado.get("error_detail")):
            # Seguir solo acumularía fallos: lo que falta queda para mañana.
            resultado.pendientes_por_tope += len(lote) - i
            resultado.errores.append("Se agotó la cuota diaria gratuita de Gemini; Sabueso sigue mañana.")
            break
        else:
            motivo = estado.get("error_detail") or estado.get("registration_status")
            resultado.descartadas.append(f"{oferta.titulo}: {motivo}")

    return resultado
