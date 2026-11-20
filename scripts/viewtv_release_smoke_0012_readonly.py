"""Prueba GET sin credenciales para la primera versión utilizable de VIEWTV.

No inicia torrents, no autentica usuarios ni modifica la SQLite.
Solo funciona contra localhost:3000/8000/8097.
"""

import json
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

OPENER = build_opener(ProxyHandler({}))


def request(url, expected):
    try:
        with OPENER.open(Request(url, method="GET"), timeout=8) as reply:
            code = reply.status
            raw = reply.read(65536)
            content_type = reply.headers.get("content-type", "")
    except HTTPError as err:
        code = err.code
        raw = err.read(4096)
        content_type = err.headers.get("content-type", "")

    if code != expected:
        raise RuntimeError(f"{url}: HTTP {code}, esperado {expected}")
    return raw, content_type


def main():
    base = "http://127.0.0.1"
    html, kind = request(f"{base}:3000/", 200)
    if "text/html" not in kind or not html.strip():
        raise RuntimeError("Interfaz vacía o sin HTML")
    print("PASS: interfaz HTML 200")

    for port, path in [(8000, "/health"), (3000, "/api/viewtv/health")]:
        body, kind = request(f"{base}:{port}{path}", 200)
        if "application/json" not in kind:
            raise RuntimeError("Health no es JSON")
        if json.loads(body) != {"estado": "ok", "servicio": "viewtv-api"}:
            raise RuntimeError("Health inesperado")
        print(f"PASS: API salud {port}{path}")

    data, _ = request(f"{base}:3000/api/viewtv/auth/profiles", 200)
    profiles = json.loads(data)
    if set(profiles) != {"perfiles"} or not isinstance(profiles["perfiles"], list):
        raise RuntimeError("Contrato de perfiles incorrecto")
    print("PASS: perfiles por proxy, sin exponer nombres")

    for path in (
        "/auth/me",
        "/solicitudes",
        "/solicitudes/descargas",
        "/jellyfin/status",
        "/jellyfin/catalog",
    ):
        request(f"{base}:3000/api/viewtv{path}", 401)
        print(f"PASS: acceso protegido sin sesión {path} -> 401")

    body, _ = request(f"{base}:8097/health", 200)
    if not body:
        raise RuntimeError("Jellyfin health vacío")
    print("PASS: Jellyfin health 200")
    print("SMOKE_READONLY=10_PASS")


if __name__ == "__main__":
    main()
