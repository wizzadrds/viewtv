"""Solo métricas NO secretas del Compose calculado; stdin JSON privado."""
import json
import sys

data = json.load(sys.stdin)
for name in ("api", "worker"):
    service = data["services"][name]
    print(f"SERVICE={name}")
    print(f"IMAGE={service.get('image')}")
    env = service.get("environment", {})
    for key in (
        "VIEWTV_WINDOWS_PUBLICATION_MODE",
        "VIEWTV_ENABLE_ORGANIZATION",
        "VIEWTV_ENABLE_AUTO_DOWNLOAD",
        "VIEWTV_AUTO_DOWNLOAD_AFTER_ID",
        "VIEWTV_ENABLE_DOWNLOAD_VERIFICATION",
        "VIEWTV_ENABLE_DOWNLOAD_START",
        "VIEWTV_ENABLE_TORRENT_SUBMIT",
    ):
        if key in env:
            print(f"{key}={env[key]}")
    for volume in service.get("volumes", []):
        if volume["target"] in ("/media", "/data", "/cache"):
            print(
                f"MOUNT_TARGET={volume['target']};TYPE={volume['type']};"
                f"READ_ONLY={volume.get('read_only', False)}"
            )
