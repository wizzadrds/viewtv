"""Valida Compose internamente sin imprimir variables ni secretos."""
import json
import sys

payload = json.load(sys.stdin)
services = payload["services"]
mode = sys.argv[1]
assert mode in ("new", "previous")
expected_api = (
    "viewtv:categorias-0013-api-conservative"
    if mode == "new" else "viewtv:auto-publicador-api-0013"
)
expected_frontend = (
    "viewtv-frontend:categorias-0013-candidate"
    if mode == "new" else "viewtv-frontend:hls-video-ref-0012"
)
api = services["api"]
worker = services["worker"]
frontend = services["frontend"]
assert api["image"] == expected_api
assert frontend["image"] == expected_frontend
assert worker["image"] == "viewtv:release-0013-worker-candidate"
env = api["environment"]
assert env["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "general"
assert str(env["VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"]) == "3"
assert str(env["VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED"]).lower() == "true"
assert worker["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "disabled"
assert str(worker["environment"]["VIEWTV_ENABLE_ORGANIZATION"]).lower() == "false"
assert str(worker["environment"]["VIEWTV_ENABLE_AUTO_DOWNLOAD"]).lower() == "true"
assert str(worker["environment"]["VIEWTV_ENABLE_DOWNLOAD_START"]).lower() == "false"
assert str(worker["environment"]["VIEWTV_ENABLE_DOWNLOAD_VERIFICATION"]).lower() == "true"
for service in (api, worker):
    media = [
        v for v in service["volumes"]
        if v["target"] == "/media"
    ]
    assert len(media) == 1 and media[0]["read_only"] is True
print("COMPOSE_CATEGORIAS_VALIDADO=SI")
print("MODO="+mode)
print("API_IMAGE="+expected_api)
print("FRONTEND_IMAGE="+expected_frontend)
print("WORKER_INTACTO=SI")
print("PUBLICADOR_LIMITADO_SOLO_ID_MAYOR_3=SI")
