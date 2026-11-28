"""Diagnóstico privado de TMDB_API_KEY en el .env productivo.

Solo lee la variable elegida para comprobar su presencia y formato,
NUNCA imprime contenido, prefijos, longitudes, rutas de usuario o secretos.
"""
import re
from pathlib import Path

file = Path("/home/viewtv/projects/viewtv/.env")
if not file.is_file() or file.is_symlink():
    raise SystemExit("ENV_PRESENTE=NO")
if file.stat().st_mode & 0o077:
    raise SystemExit("ENV_PERMISOS_PRIVADOS=NO")
lines = file.read_text(encoding="utf-8-sig").splitlines()
definitions = []
for line in lines:
    match = re.fullmatch(r"\s*TMDB_API_KEY\s*=\s*(.*?)\s*", line)
    if match:
        value = match.group(1).strip().strip("\"'")
        definitions.append(value)
if not definitions:
    print("TMDB_CLAVE_EN_ENV=NO_DEFINIDA")
elif len(definitions) != 1:
    print("TMDB_CLAVE_EN_ENV=DEFINICION_DUPLICADA")
elif not definitions[0]:
    print("TMDB_CLAVE_EN_ENV=VACIA")
elif definitions[0].startswith("eyJ") and definitions[0].count(".") >= 2:
    print("TMDB_CLAVE_EN_ENV=TOKEN_V4_NO_APTO_PARA_V3")
elif re.fullmatch(r"[0-9a-fA-F]{32}", definitions[0]):
    print("TMDB_CLAVE_EN_ENV=API_KEY_V3_FORMATO_VALIDO")
else:
    print("TMDB_CLAVE_EN_ENV=FORMATO_NO_RECONOCIDO")
