"""Comprobación productiva solo lectura, sin cuentas ni secretos."""
import os
import stat
from pathlib import Path

import httpx
from app.cache_privada import estado_cache
from app.config import get_settings

root = Path("/cache-gestionada")
media = Path("/media")
info = os.stat(root, follow_symlinks=False)
assert stat.S_ISDIR(info.st_mode)
assert info.st_uid == os.geteuid()
assert info.st_mode & 0o022 == 0
assert info.st_dev != os.stat(media, follow_symlinks=False).st_dev
print("CACHE_VOLUMEN_INDEPENDIENTE=PASS")

quota = get_settings().cache_quota_gb * 1024**3
status = estado_cache(root, quota)
assert status["estado"] == "vacia_sin_inicializar"
assert status["archivos"] == 0
assert status["bytes"] == 0
print("CACHE_PRIVADA_VACIA=SI")
print("CACHE_CUOTA_PROPIA_GIB=" + str(quota // 1024**3))

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
    get = client.get("/almacenamiento/resumen")
    assert get.status_code == 401
    print("RESUMEN_SIN_SESION=401")
    post = client.post(
        "/almacenamiento/cache/propia/limpiar",
        json={"confirmacion": "LIMPIAR CACHE PROPIA"},
    )
    assert post.status_code == 401
    print("LIMPIAR_CACHE_SIN_SESION=401")
    assert client.get("/health").status_code == 200
    print("API_SALUD=200")
print("ESCRITURAS_MEDIA_O_CACHE=0")
