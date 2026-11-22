"""Comprueba Compose sin revelar API keys ni variables secretas."""
import json
import sys

target = sys.argv[1]
assert target in ("new", "previous")
services = json.load(sys.stdin)["services"]
assert services["api"]["image"] == "viewtv:series-episodios-api-0013"
assert services["worker"]["image"] == "viewtv:release-0013-worker-candidate"
assert services["catalogador"]["image"] == "viewtv:catalogo-escalable-api-0013"
expected = ("viewtv-frontend:tv-auto-update-0013"
            if target == "new" else "viewtv-frontend:series-episodios-0013")
assert services["frontend"]["image"] == expected
api = services["api"]
assert api["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "general"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"]) == "3"
assert str(api["environment"]["VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED"]).lower() == "true"
worker = services["worker"]
assert worker["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "disabled"
assert str(worker["environment"]["VIEWTV_ENABLE_ORGANIZATION"]).lower() == "false"
assert str(worker["environment"]["VIEWTV_ENABLE_DOWNLOAD_START"]).lower() == "false"
assert services["catalogador"]["user"] == "1000:1000"
assert services["catalogador"]["read_only"] is True
assert services["catalogador"]["cap_drop"] == ["ALL"]
assert "no-new-privileges:true" in services["catalogador"]["security_opt"]
assert "ports" not in services["catalogador"]
for service in ("api", "worker"):
    media = [v for v in services[service]["volumes"] if v["target"] == "/media"]
    assert len(media) == 1 and media[0]["read_only"] is True
print("TV_COMPOSE_"+target+"=PASS")
print("API_WORKER_JELLYFIN_NO_CAMBIAN=SI")
print("MEDIOS_Y_PUBLICADOR_PROTEGIDOS=SI")
