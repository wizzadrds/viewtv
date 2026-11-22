"""Valida Compose 0014 sin mostrar las claves privadas ni rutas de torrents."""
import json
import re
import sys

mode = sys.argv[1]
assert mode in ("new", "previous", "rollback")
services = json.load(sys.stdin)["services"]
api = services["api"]
worker = services["worker"]
frontend = services["frontend"]
catalogador = services["catalogador"]
expected = {
    "new": ("viewtv:cohesion-caratula-api-0014", "viewtv:cohesion-caratula-worker-0014"),
    "previous": ("viewtv:busqueda-tmdb-api-0013", "viewtv:busqueda-tmdb-worker-0013"),
    "rollback": ("viewtv:cohesion-rollback-api-0014", "viewtv:cohesion-rollback-worker-0014"),
}[mode]
assert (api["image"], worker["image"]) == expected
assert frontend["image"] == "viewtv-frontend:samsung-busqueda-0013"
assert catalogador["image"] == "viewtv:catalogo-escalable-api-0013"

assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"]) == "general"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"]) == "3"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED"]).lower() == "true"
assert str(worker["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"]) == "disabled"
for flag in ("VIEWTV_ENABLE_ORGANIZATION", "VIEWTV_ENABLE_DOWNLOAD_START",
             "VIEWTV_ENABLE_TORRENT_SUBMIT"):
    assert str(worker["environment"][flag]).lower() == "false"

assert re.fullmatch(r"[0-9a-fA-F]{32}", api["environment"]["TMDB_API_KEY"])
assert worker["environment"]["TMDB_API_KEY"] == api["environment"]["TMDB_API_KEY"]
for service in (api, worker):
    media = [v for v in service["volumes"] if v["target"] == "/media"]
    assert len(media) == 1 and media[0]["read_only"] is True
assert catalogador["read_only"] is True
assert catalogador["cap_drop"] == ["ALL"]
assert "no-new-privileges:true" in catalogador["security_opt"]
print("COMPOSE_COHESION_0014=" + mode)
print("API_WORKER_MISMA_VERSION=SI")
print("CLAVES_NO_PUBLICADAS=SI")
print("FRONTEND_Y_CATALOGADOR_INTACTOS=SI")
