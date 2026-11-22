"""Invariantes de despliegue para búsqueda multilingüe y Samsung TV."""
import json
import re
import sys

mode = sys.argv[1]
assert mode in ("new", "previous")
services = json.load(sys.stdin)["services"]
api = services["api"]
worker = services["worker"]
frontend = services["frontend"]
catalogador = services["catalogador"]
images = (
    ("viewtv:busqueda-tmdb-api-0013",
     "viewtv:busqueda-tmdb-worker-0013",
     "viewtv-frontend:samsung-busqueda-0013")
    if mode == "new"
    else ("viewtv:series-episodios-api-0013",
          "viewtv:release-0013-worker-candidate",
          "viewtv-frontend:tv-auto-update-0013")
)
assert tuple(x["image"] for x in (api, worker, frontend)) == images
assert catalogador["image"] == "viewtv:catalogo-escalable-api-0013"
assert api["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "general"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"]) == "3"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED"]).lower() == "true"
assert worker["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "disabled"
assert str(worker["environment"]["VIEWTV_ENABLE_ORGANIZATION"]).lower() == "false"
assert str(worker["environment"]["VIEWTV_ENABLE_DOWNLOAD_START"]).lower() == "false"
assert str(worker["environment"]["VIEWTV_ENABLE_TORRENT_SUBMIT"]).lower() == "false"
assert catalogador["user"] == "1000:1000"
assert catalogador["read_only"] is True
assert catalogador["cap_drop"] == ["ALL"]
assert "no-new-privileges:true" in catalogador["security_opt"]
assert "ports" not in catalogador
assert re.fullmatch(r"[0-9a-fA-F]{32}", api["environment"]["TMDB_API_KEY"])
if mode == "new":
    assert re.fullmatch(r"[0-9a-fA-F]{32}", worker["environment"]["TMDB_API_KEY"])
    assert worker["environment"]["TMDB_API_KEY"] == api["environment"]["TMDB_API_KEY"]
for service in (api, worker):
    media = [v for v in service["volumes"] if v["target"] == "/media"]
    assert len(media) == 1 and media[0]["read_only"] is True
cache = [v for v in api["volumes"] if v["target"] == "/catalogo"]
assert len(cache) == 1 and cache[0]["read_only"] is True
assert len(catalogador["volumes"]) == 1
assert catalogador["volumes"][0]["source"] == cache[0]["source"]
print("BUSQUEDA_SAMSUNG_COMPOSE="+mode)
print("TMDB_EN_API_Y_WORKER="+("SI" if mode=="new" else "NO_APLICA"))
print("PUBLICADOR_Y_MEDIOS_CONSERVADOS=SI")
print("CATALOGADOR_SEPARADO=SI")
