"""Comprueba Compose previo y nuevo, SIN revelar variables secretas."""
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
expected = (
    "viewtv:catalogo-escalable-api-0013"
    if mode == "new" else "viewtv:catalogo-amplio-api-0013"
)
assert api["image"] == expected
assert catalogador["image"] == expected
assert frontend["image"] == "viewtv-frontend:catalogo-amplio-0013"
assert worker["image"] == "viewtv:release-0013-worker-candidate"
assert api["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "general"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"]) == "3"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED"]).lower() == "true"
if mode == "new":
    configured = str(api["environment"]["VIEWTV_CATALOG_MAX_ITEMS"])
    assert configured.isdecimal() and 20_000 <= int(configured) <= 1_000_000
    assert str(catalogador["environment"]["VIEWTV_CATALOG_MAX_ITEMS"]) == configured
assert worker["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "disabled"
assert str(worker["environment"]["VIEWTV_ENABLE_ORGANIZATION"]).lower() == "false"
assert str(worker["environment"]["VIEWTV_ENABLE_DOWNLOAD_START"]).lower() == "false"
for service in (api, worker):
    media = [v for v in service["volumes"] if v["target"] == "/media"]
    assert len(media) == 1 and media[0]["read_only"] is True
api_cache = [v for v in api["volumes"] if v["target"] == "/catalogo"]
assert len(api_cache) == 1 and api_cache[0]["read_only"] is True
assert catalogador["read_only"] is True
assert catalogador["user"] == "1000:1000"
assert catalogador["cap_drop"] == ["ALL"]
assert "no-new-privileges:true" in catalogador["security_opt"]
assert "privileged" not in catalogador or catalogador["privileged"] is False
assert "ports" not in catalogador
assert len(catalogador["volumes"]) == 1
assert catalogador["volumes"][0]["target"] == "/catalogo"
assert catalogador["volumes"][0]["source"] == api_cache[0]["source"]
assert not catalogador["volumes"][0].get("read_only", False)
assert re.fullmatch(r"[0-9a-fA-F]{32}", catalogador["environment"]["TMDB_API_KEY"])
assert catalogador["environment"].keys() <= {
    "TMDB_API_KEY", "TMDB_LANGUAGE", "VIEWTV_CATALOG_PATH",
    "VIEWTV_CATALOG_MAX_ITEMS", "PYTHONDONTWRITEBYTECODE",
}
assert api["environment"]["VIEWTV_CATALOG_PATH"] == "/catalogo/metadatos.db"
assert catalogador["environment"]["VIEWTV_CATALOG_PATH"] == "/catalogo/metadatos.db"
print("COMPOSE_ESCALABLE=" + mode)
print("API_CATALOGO_COMPARTEN_SOLO_LECTURA=SI")
print("WORKER_Y_PUBLICADOR_INTACTOS=SI")
print("MEDIOS_PROTEGIDOS=SI")
print("CATALOGADOR_SIN_ACCESO_A_MEDIOS=SI")
