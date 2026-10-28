"""
Levanta todo lo que la app necesita con un solo comando:

    python -m scripts.iniciar

    - API (FastAPI) en http://localhost:8000  -> recibe las ofertas del marcador
    - App (Streamlit) en http://localhost:8501 -> se abre sola en el navegador

Si alguna ya está corriendo (por ejemplo, abriste la app antes con
`streamlit run`), la reutiliza y solo levanta lo que falta.
Ctrl + C cierra lo que este comando abrió.
"""

import socket
import subprocess
import sys
import time

from app.cv.cargador import RAIZ

PUERTO_API = 8000
PUERTO_APP = 8501


def puerto_ocupado(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def main() -> int:
    python = sys.executable
    procesos = []

    if puerto_ocupado(PUERTO_API):
        print(f"API: ya estaba corriendo en http://localhost:{PUERTO_API}")
    else:
        procesos.append(subprocess.Popen(
            [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PUERTO_API)],
            cwd=RAIZ,
        ))
        print(f"API: iniciada en http://localhost:{PUERTO_API}")

    if puerto_ocupado(PUERTO_APP):
        print(f"App: ya estaba abierta en http://localhost:{PUERTO_APP} (la reutilizo)")
    else:
        procesos.append(subprocess.Popen(
            [python, "-m", "streamlit", "run", "streamlit_app.py", "--server.port", str(PUERTO_APP)],
            cwd=RAIZ,
        ))
        print(f"App: iniciada en http://localhost:{PUERTO_APP}")

    if not procesos:
        print("Todo ya estaba corriendo. No hay nada que iniciar.")
        return 0

    print("Ctrl + C para cerrar lo que se inició aquí.")
    try:
        while all(p.poll() is None for p in procesos):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for proceso in procesos:
            if proceso.poll() is None:
                proceso.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
