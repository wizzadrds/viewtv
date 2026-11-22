"""Verificación privada del Compose, nunca expone valores del .env."""
import json
import re
import sys

mode = sys.argv[1]
assert mode in ("new", "previous")
config = json.load(sys.stdin)
services = config["services"]
api = services["api"]
frontend = services["frontend"]
worker = services["worker"]
catalogador = services["catalogador"]

if mode == "new":
    assert api["image"] == "viewtv:series-episodios-api-0013"
    assert frontend["image"] == "viewtv-frontend:series-episodios-0013"
else:
    assert api["image"] == "viewtv:catalogo-escalable-api-0013"
    assert frontend["image"] == "viewtv-frontend:catalogo-amplio-0013"

assert catalogador["image"] == "viewtv:catalogo-escalable-api-0013"
assert worker["image"] == "viewtv:release-0013-worker-candidate"
assert api["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "general"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"]) == "3"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED"]).lower() == "true"
assert str(api["environment"]["VIEWTV_CATALOG_MAX_ITEMS"]) == "250000"
assert str(catalogador["environment"]["VIEWTV_CATALOG_MAX_ITEMS"]) == "250000"
assert worker["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "disabled"
assert str(worker["environment"]["VIEWTV_ENABLE_ORGANIZATION"]).lower() == "false"
assert str(worker["environment"]["VIEWTV_ENABLE_DOWNLOAD_START"]).lower() == "false"
assert catalogador["user"] == "1000:1000"
assert catalogador["read_only"] is True
assert catalogador["cap_drop"] == ["ALL"]
assert "no-new-privileges:true" in catalogador["security_opt"]
assert "ports" not in catalogador
assert re.fullmatch(r"[0-9a-fA-F]{32}", catalogador["environment"]["TMDB_API_KEY"])
assert api["environment"].get("TMDB_API_KEY")
for service in (api, worker):
    media = [v for v in service["volumes"] if v["target"] == "/media"]
    assert len(media) == 1 and media[0]["read_only"] is True
api_catalog = [v for v in api["volumes"] if v["target"] == "/catalogo"]
assert len(api_catalog) == 1 and api_catalog[0]["read_only"] is True
assert len(catalogador["volumes"]) == 1
assert catalogador["volumes"][0]["target"] == "/catalogo"
assert catalogador["volumes"][0]["source"] == api_catalog[0]["source"]
assert not catalogador["volumes"][0].get("read_only", False)
print("COMPOSE_SERIES_"+mode+"=OK")
print("API_MEDIOS_SOLO_LECTURA=SI")
print("CATALOGADOR_Y_WORKER_SIN_CAMBIOS=SI")
print("PUBLICADOR_GENERAL_AFTER_ID_3=CONSERVADO")
