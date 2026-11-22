"""Comprueba Compose efectivo sin imprimir credenciales ni datos de usuarios."""
import json
import re
import sys

mode = sys.argv[1]
expected = {
    "new": (
        "viewtv:gestion-espacio-api-0015",
        "viewtv:gestion-espacio-worker-0015",
        "viewtv-frontend:gestion-espacio-0015",
    ),
    "rollback": (
        "viewtv:gestion-espacio-rollback-api-0015",
        "viewtv:gestion-espacio-rollback-worker-0015",
        "viewtv-frontend:samsung-busqueda-0013",
    ),
}[mode]
services = json.load(sys.stdin)["services"]
api = services["api"]
worker = services["worker"]
frontend = services["frontend"]
catalogador = services["catalogador"]
assert (api["image"], worker["image"], frontend["image"]) == expected
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
    cache = [v for v in service["volumes"] if v["target"] == "/cache"]
    if cache:
        assert len(cache) == 1
assert catalogador["read_only"] is True
assert catalogador["cap_drop"] == ["ALL"]
assert "no-new-privileges:true" in catalogador["security_opt"]
print("GESTION_ESPACIO_COMPOSE=" + mode)
print("API_WORKER_MISMO_ESQUEMA=SI")
print("TAREAS_Y_POLITICAS_PREEXISTENTES=IGUALES")
print("MEDIOS_SIN_ESCRITURA_EN_API_WORKER=SI")
