"""
centinela.py -- agente Centinela

Tarea fija: vigilar y avisar. Arma un resumen con

    - las ofertas registradas en las últimas 24 h (lo que trajo
      Sabueso o analizaste tú), de mejor a peor Match Score;
    - las postulaciones sin movimiento hace más de N días, para
      que hagas seguimiento;

lo guarda como Markdown en salidas/resumenes/ y te avisa con una
notificación de Windows. Sin LLM. Nunca envía nada por ti.
"""

import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from app import consultas
from app.cv.cargador import RAIZ

CARPETA_RESUMENES = RAIZ / "salidas" / "resumenes"
TOP_NUEVAS = 5
DIAS_SIN_RESPUESTA = 7


def armar_resumen(horas: int = 24, dias_sin_respuesta: int = DIAS_SIN_RESPUESTA) -> dict:
    return {
        "fecha": date.today().isoformat(),
        "nuevas": consultas.ofertas_recientes(horas),
        "recordatorios": consultas.postulaciones_sin_movimiento(dias_sin_respuesta),
        "dias_sin_respuesta": dias_sin_respuesta,
    }


def _score(valor: Optional[float]) -> str:
    return f"{valor:.0f}%" if valor is not None else "sin score"


def resumen_markdown(resumen: dict, sabueso: Optional[dict] = None) -> str:
    lineas = [f"# Resumen de Job-Intelligence — {resumen['fecha']}", ""]

    if sabueso is not None:
        lineas += [
            "## Sabueso",
            f"- Ofertas encontradas: {sabueso['encontradas']} "
            f"(fuera de filtro: {sabueso['fuera_de_filtro']}, ya registradas: {sabueso['ya_registradas']})",
            f"- Registradas hoy: {len(sabueso['registradas'])}",
        ]
        if sabueso["descartadas"]:
            lineas.append(
                f"- No se pudieron registrar {len(sabueso['descartadas'])} (Gemini saturado u oferta cerrada); "
                "las que fallaron por Gemini se reintentan en la próxima corrida."
            )
        if sabueso["pendientes_por_tope"]:
            lineas.append(f"- Quedaron {sabueso['pendientes_por_tope']} para mañana (tope diario de Gemini).")
        for error in sabueso["errores"]:
            lineas.append(f"- Error: {error}")
        lineas.append("")

    nuevas = resumen["nuevas"]
    lineas.append(f"## Mejores ofertas nuevas ({len(nuevas)})")
    if not nuevas:
        lineas.append("No hay ofertas nuevas en las últimas 24 horas.")
    for o in nuevas[:TOP_NUEVAS]:
        enlace = f" — {o['url']}" if o.get("url") else ""
        lineas.append(f"- **{_score(o['match_score'])}** · {o['puesto']} · {o['empresa']}{enlace}")
    lineas.append("")

    recordatorios = resumen["recordatorios"]
    lineas.append(f"## Seguimiento ({len(recordatorios)})")
    if not recordatorios:
        lineas.append(f"Ninguna postulación lleva más de {resumen['dias_sin_respuesta']} días sin movimiento.")
    for r in recordatorios:
        lineas.append(f"- {r['puesto']} · {r['empresa']}: {r['dias']} días sin respuesta.")
    return "\n".join(lineas) + "\n"


def guardar_resumen(texto: str, fecha: str, carpeta: Optional[Path] = None) -> Path:
    carpeta = carpeta or CARPETA_RESUMENES
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"resumen_{fecha}.md"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def texto_notificacion(resumen: dict) -> tuple[str, str]:
    nuevas, recordatorios = resumen["nuevas"], resumen["recordatorios"]
    titulo = f"{len(nuevas)} oferta(s) nueva(s)"
    if nuevas:
        mejor = nuevas[0]
        cuerpo = f"La mejor: {mejor['puesto']} ({_score(mejor['match_score'])})."
    else:
        cuerpo = "Hoy no llegaron ofertas nuevas."
    if recordatorios:
        cuerpo += f" {len(recordatorios)} postulación(es) para hacer seguimiento."
    return titulo, cuerpo


# PowerShell 5.1 trae las clases de notificación de Windows; el AppId
# es el de PowerShell, así no hace falta registrar una app propia.
_SCRIPT_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$env:JI_TITULO</text><text>$env:JI_CUERPO</text></binding></visual></toast>")
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
"""


def notificar(titulo: str, cuerpo: str) -> bool:
    """Notificación de Windows. Devuelve False (sin lanzar) si no se pudo."""
    if os.name != "nt":
        return False
    entorno = {**os.environ, "JI_TITULO": escape(f"Job-Intelligence: {titulo}"), "JI_CUERPO": escape(cuerpo)}
    try:
        proceso = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT_TOAST],
            env=entorno, capture_output=True, timeout=30,
        )
        return proceso.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
