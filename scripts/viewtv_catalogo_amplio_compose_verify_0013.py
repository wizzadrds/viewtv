"""Verifica el Compose de catálogo sin revelar secretos ni datos de usuario."""
import json
import re
import sys

mode = sys.argv[1]
assert mode in ("new", "previous")
config = json.load(sys.stdin)
api = config["services"]["api"]
frontend = config["services"]["frontend"]
worker = config["services"]["worker"]
if mode == "new":
    assert api["image"] == "viewtv:catalogo-amplio-api-0013"
    assert frontend["image"] == "viewtv-frontend:catalogo-amplio-0013"
    catalogador = config["services"]["catalogador"]
    assert catalogador["image"] == api["image"]
    assert catalogador["user"] == "1000:1000"
    assert catalogador["read_only"] is True
    assert catalogador["command"] == ["python", "-m", "app.catalogador_cli", "loop"]
    assert catalogador["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in catalogador["security_opt"]
    assert "ports" not in catalogador
    assert "privileged" not in catalogador or catalogador["privileged"] is False
    assert catalogador["environment"]["VIEWTV_CATALOG_PATH"] == "/catalogo/metadatos.db"
    key = catalogador["environment"]["TMDB_API_KEY"]
    assert re.fullmatch(r"[0-9a-fA-F]{32}", key)
    assert catalogador["environment"].keys() <= {
        "TMDB_API_KEY", "TMDB_LANGUAGE", "VIEWTV_CATALOG_PATH",
        "PYTHONDONTWRITEBYTECODE",
    }
    assert len(catalogador["volumes"]) == 1
    assert catalogador["volumes"][0]["target"] == "/catalogo"
    assert catalogador["volumes"][0].get("read_only", False) is False
    api_catalog = [v for v in api["volumes"] if v["target"] == "/catalogo"]
    assert len(api_catalog) == 1 and api_catalog[0]["read_only"] is True
    assert catalogador["volumes"][0]["source"] == api_catalog[0]["source"]
    assert api["environment"]["VIEWTV_CATALOG_PATH"] == "/catalogo/metadatos.db"
else:
    assert api["image"] == "viewtv:categorias-0013-api-conservative"
    assert frontend["image"] == "viewtv-frontend:categorias-0013-candidate"
    assert "catalogador" not in config["services"]

assert worker["image"] == "viewtv:release-0013-worker-candidate"
assert api["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "general"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"]) == "3"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED"]).lower() == "true"
assert worker["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "disabled"
assert str(worker["environment"]["VIEWTV_ENABLE_ORGANIZATION"]).lower() == "false"
assert str(worker["environment"]["VIEWTV_ENABLE_DOWNLOAD_START"]).lower() == "false"
for service in (api, worker):
    media = [v for v in service["volumes"] if v["target"] == "/media"]
    assert len(media) == 1 and media[0]["read_only"] is True

print("COMPOSE_CATALOGO="+mode)
print("POLITICA_PUBLICADOR=CONSERVADA")
print("VOLUMEN_MEDIOS_SOLO_LECTURA=SI")
if mode == "new":
    print("CATALOGADOR_SIN_MEDIOS_SIN_DB_PRINCIPAL=SI")
    print("VOLUMEN_CATALOGO_INDEPENDIENTE=SI")
