"""Audita exclusivamente Compose efectivo, sin mostrar secretos."""
import json
import sys

s = json.load(sys.stdin)["services"]
assert s["api"]["image"] == "viewtv:publicador-compatible-api-0016"
assert s["worker"]["image"] == "viewtv:gestion-espacio-worker-0015"
assert s["frontend"]["image"] == "viewtv-frontend:gestion-espacio-0015"
assert s["catalogador"]["image"] == "viewtv:catalogo-escalable-api-0013"
assert s["api"]["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "general"
assert str(s["api"]["environment"]["VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"]) == "3"
assert str(s["api"]["environment"]["VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED"]).lower() == "true"
assert s["worker"]["environment"]["VIEWTV_WINDOWS_PUBLICATION_MODE"] == "disabled"
for flag in ("VIEWTV_ENABLE_ORGANIZATION", "VIEWTV_ENABLE_DOWNLOAD_START",
             "VIEWTV_ENABLE_TORRENT_SUBMIT"):
    assert str(s["worker"]["environment"][flag]).lower() == "false"
for service in ("api", "worker"):
    mount = [v for v in s[service]["volumes"] if v["target"] == "/media"]
    assert len(mount) == 1 and mount[0]["read_only"] is True
assert s["catalogador"]["read_only"] is True
assert s["catalogador"]["cap_drop"] == ["ALL"]
print("COMPOSE_COMPAT_PUBLICADOR=PASS")
