"""Comprueba Compose antes de recargar la clave TMDB; nunca imprime secretos."""
import json
import re
import sys

config = json.load(sys.stdin)
services = config["services"]
api = services["api"]
frontend = services["frontend"]
worker = services["worker"]

if api["image"] != "viewtv:categorias-0013-api-conservative":
    raise SystemExit("IMAGEN_API_NO_AUTORIZADA")
if frontend["image"] != "viewtv-frontend:categorias-0013-candidate":
    raise SystemExit("IMAGEN_FRONTEND_NO_AUTORIZADA")
if worker["image"] != "viewtv:release-0013-worker-candidate":
    raise SystemExit("IMAGEN_WORKER_NO_AUTORIZADA")

env = api["environment"]
key = env.get("TMDB_API_KEY", "")
if not isinstance(key, str) or re.fullmatch(r"[a-fA-F0-9]{32}", key) is None:
    raise SystemExit("TMDB_V3_NO_CONFIGURADA")
if env.get("VIEWTV_WINDOWS_PUBLICATION_MODE") != "general":
    raise SystemExit("POLITICA_PUBLICADOR_CAMBIADA")
if str(env.get("VIEWTV_WINDOWS_PUBLICATION_AFTER_ID")) != "3":
    raise SystemExit("UMBRAL_PUBLICADOR_CAMBIADO")
if str(env.get("VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED")).lower() != "true":
    raise SystemExit("AUTORIZACION_PUBLICADOR_CAMBIADA")
wenv = worker["environment"]
if wenv.get("VIEWTV_WINDOWS_PUBLICATION_MODE") != "disabled":
    raise SystemExit("WORKER_PUBLICADOR_INESPERADO")
if str(wenv.get("VIEWTV_ENABLE_ORGANIZATION")).lower() != "false":
    raise SystemExit("ORGANIZACION_WORKER_INESPERADA")
for service in (api, worker):
    media = [v for v in service["volumes"] if v["target"] == "/media"]
    if len(media) != 1 or media[0]["read_only"] is not True:
        raise SystemExit("MONTAJE_MEDIA_NO_ES_SOLO_LECTURA")
print("TMDB_COMPOSE_CLAVE_V3=CONFIGURADA")
print("IMAGENES_CANDIDATAS=VALIDADAS")
print("PUBLICADOR_AFTER_ID_3=CONSERVADO")
print("MEDIOS_SOLO_LECTURA=CONFIRMADO")
