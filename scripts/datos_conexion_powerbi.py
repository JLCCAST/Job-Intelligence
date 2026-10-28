"""
datos_conexion_powerbi.py

Desglosa tu SUPABASE_DB_URL en los campos que pide el conector de
PostgreSQL de Power BI. NO imprime la contraseña completa.

Correr desde la raíz del proyecto, con el venv activo:
    python -m scripts.datos_conexion_powerbi
"""

import os
from urllib.parse import urlparse, unquote

from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_DB_URL")
if not url:
    raise SystemExit("No encontré SUPABASE_DB_URL en el .env")

p = urlparse(url)
host = p.hostname or ""
port = p.port or 5432
usuario = unquote(p.username or "")
password = unquote(p.password or "")
base = (p.path or "/postgres").lstrip("/")

print("=" * 64)
print("DATOS PARA EL CONECTOR PostgreSQL DE POWER BI")
print("=" * 64)
print()
print("  Obtener datos > Base de datos PostgreSQL")
print()
print(f"  Servidor    : {host}:{port}")
print(f"  Base de datos : {base}")
print()
print("  (pestaña de credenciales, método 'Base de datos')")
print(f"  Usuario     : {usuario}")
print(f"  Contraseña  : {'*' * 8}{password[-3:] if len(password) > 3 else ''}"
      "   <- cópiala del .env, no de aquí")
print()

# --- Verificación del modo de conexión ---
print("=" * 64)
print("VERIFICACIÓN")
print("=" * 64)

if port == 6543:
    print("  [!] Puerto 6543 = Transaction pooler.")
    print("      Power BI usa prepared statements y este modo las")
    print("      descarta entre consultas -> errores intermitentes")
    print("      y difíciles de diagnosticar.")
    print("      Ve al dashboard de Supabase > Connect y copia la")
    print("      cadena del 'Session pooler' (puerto 5432).")
elif "pooler" in host:
    print("  [OK] Session pooler en 5432: es el modo correcto para Power BI.")
else:
    print("  [OK] Conexión directa. Funciona, pero requiere IPv6.")
    print("       Si Power BI no logra conectar, usa el Session pooler.")

print()
print("  En el cuadro de conexión elige IMPORT, no DirectQuery.")
print("  (volumen chico + plan gratuito de Supabase)")
print()
print("=" * 64)
print("TABLAS A IMPORTAR (las 10 del modelo)")
print("=" * 64)
for t in [
    "company", "company_alias", "source", "status", "job",
    "job_status_history", "technology", "technology_alias",
    "job_technology", "user_skill",
]:
    print(f"    public.{t}")
print()
print("  Marca las 10 en el Navegador y dale 'Cargar'.")
