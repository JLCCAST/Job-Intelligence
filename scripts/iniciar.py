"""
Abre Job-Intelligence con un solo comando:

    python -m scripts.iniciar

Levanta el servidor en http://localhost:8000, que sirve la app (React,
ya compilada), la API y el endpoint del marcador del navegador. Si el
frontend cambió desde la última compilación, lo compila antes (necesita
Node.js; la primera vez también instala sus dependencias).

Ctrl + C lo cierra.
"""

import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from app.cv.cargador import RAIZ

PUERTO = 8000
WEB = RAIZ / "web"
DIST = WEB / "dist" / "index.html"


def puerto_ocupado(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def frontend_desactualizado() -> bool:
    if not DIST.exists():
        return True
    compilado = DIST.stat().st_mtime
    fuentes = [WEB / "index.html", WEB / "package.json", *(WEB / "src").rglob("*")]
    return any(f.is_file() and f.stat().st_mtime > compilado for f in fuentes)


def compilar_frontend() -> bool:
    npm = shutil.which("npm")
    if npm is None:
        print("No encontré npm (Node.js). Instálalo desde nodejs.org para compilar el frontend.")
        return DIST.exists()
    if not (WEB / "node_modules").is_dir():
        print("Instalando dependencias del frontend (solo la primera vez)...")
        subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=WEB, check=True)
    print("Compilando el frontend...")
    subprocess.run([npm, "run", "build"], cwd=WEB, check=True)
    return True


def main() -> int:
    url = f"http://localhost:{PUERTO}"
    if puerto_ocupado(PUERTO):
        print(f"Job-Intelligence ya está corriendo en {url}")
        webbrowser.open(url)
        return 0

    if frontend_desactualizado() and not compilar_frontend():
        return 1

    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PUERTO)],
        cwd=RAIZ,
    )
    # Abre el navegador cuando el servidor ya responde.
    threading.Thread(
        target=lambda: (time.sleep(2.5), webbrowser.open(url)), daemon=True,
    ).start()
    print(f"Job-Intelligence en {url}  (Ctrl + C para cerrar)")
    try:
        servidor.wait()
    except KeyboardInterrupt:
        servidor.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
