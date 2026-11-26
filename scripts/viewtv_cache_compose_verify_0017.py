"""Verifica políticas del stack sin mostrar credenciales ni rutas privadas."""
import json
import sys

mode = sys.argv[1]
expected = {
    "new": ("viewtv:cache-propia-api-0017", "viewtv-frontend:cache-propia-0017"),
    "rollback": (
        "viewtv:publicador-compatible-api-0016",
        "viewtv-frontend:gestion-espacio-0015",
    ),
}[mode]
config = json.load(sys.stdin)
services = config["services"]
api = services["api"]
worker = services["worker"]
frontend = services["frontend"]
assert (api["image"], frontend["image"]) == expected
assert worker["image"] == "viewtv:gestion-espacio-worker-0015"
assert services["catalogador"]["image"] == "viewtv:catalogo-escalable-api-0013"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"]) == "general"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"]) == "3"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED"]).lower() == "true"
assert str(worker["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"]) == "disabled"
for flag in ("VIEWTV_ENABLE_DOWNLOAD_START", "VIEWTV_ENABLE_TORRENT_SUBMIT",
             "VIEWTV_ENABLE_ORGANIZATION"):
    assert str(worker["environment"][flag]).lower() == "false"
for service in (api, worker):
    media = [v for v in service["volumes"] if v["target"] == "/media"]
    assert len(media) == 1 and media[0]["read_only"] is True
own = [v for v in api["volumes"] if v["target"] == "/cache-gestionada"]
assert len(own) == 1
assert own[0]["type"] == "volume" and own[0]["source"] == "viewtv_cache_propia_0017"
assert not own[0].get("read_only", False)
assert "viewtv_cache_propia_0017" in config["volumes"]
assert all(v["target"] != "/cache-gestionada" for v in worker["volumes"])
assert services["catalogador"]["read_only"] is True
assert services["catalogador"]["cap_drop"] == ["ALL"]
assert "no-new-privileges:true" in services["catalogador"]["security_opt"]
print("CACHE_PROPIA_COMPOSE_" + mode.upper() + "=PASS")
print("MEDIA_READ_ONLY=SI")
print("QBIT_Y_PUBLICADOR_SIN_CAMBIOS=SI")
