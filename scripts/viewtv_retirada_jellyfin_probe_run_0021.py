"""Lanza probe de dos GET en API 0017, SIN instalar código en el contenedor.

Inyecta temporalmente en memoria el evaluador 0021, no modifica volumen,
imagen, paquetes, env, base SQLite, API HTTP ni certificados.
Filtra toda la salida; no imprime usuarios, sesiones, películas ni secretos.
"""
from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_KEYS = frozenset({
    "JELLYFIN_SESIONES_0021",
    "ESTADO",
    "PELICULAS_COMPROBADAS",
    "PELICULAS_BLOQUEADAS",
    "SESIONES_JELLYFIN",
    "SESIONES_PELICULA_OBJETIVO",
    "SESIONES_OTRAS_PELICULAS",
    "SESIONES_AMBIGUAS",
    "SIN_BLOQUEO_TRANSACCIONAL",
    "AUTORIZA_BORRADO_FISICO",
    "REPRODUCCIONES_MODIFICADAS",
    "ARCHIVOS_ELIMINADOS",
})
SAFE_VALUE = re.compile(r"[A-Za-z_0-9]{1,60}\Z")


def payload() -> str:
    module = (ROOT / "worker/retirement_playback_guard_0021.py").read_bytes()
    probe = (ROOT / "scripts/viewtv_retirada_jellyfin_sesiones_0021.py").read_bytes()
    if not 100 <= len(module) <= 15_000 or not 100 <= len(probe) <= 15_000:
        raise ValueError("Código de preflight fuera de límite.")
    first = base64.b64encode(module).decode("ascii")
    second = base64.b64encode(probe).decode("ascii")
    return (
        "import base64,sys,types\n"
        "m=types.ModuleType('worker.retirement_playback_guard_0021')\n"
        f"exec(compile(base64.b64decode('{first}'), 'guard0021', 'exec'), m.__dict__)\n"
        "sys.modules['worker.retirement_playback_guard_0021']=m\n"
        f"exec(compile(base64.b64decode('{second}'), 'probe0021', 'exec'), "
        "{'__name__':'__main__'})\n"
    )


def main() -> int:
    try:
        process = subprocess.run(
            ["docker", "exec", "-i", "viewtv-api-1", "python", "-"],
            input=payload(), text=True, capture_output=True,
            timeout=35, check=False,
        )
        if process.returncode not in (0, 2):
            raise RuntimeError("No se pudo consultar sesiones.")
        lines = process.stdout.splitlines()
        if not 3 <= len(lines) <= 16:
            raise RuntimeError("Informe inválido.")
        filtered: dict[str, str] = {}
        for line in lines:
            key, sep, value = line.partition("=")
            if not sep or key not in ALLOWED_KEYS or not SAFE_VALUE.fullmatch(value):
                raise RuntimeError("Informe no confiable.")
            if key in filtered:
                raise RuntimeError("Clave de informe duplicada.")
            filtered[key] = value
        if (
            filtered.get("AUTORIZA_BORRADO_FISICO") != "NO"
            or filtered.get("REPRODUCCIONES_MODIFICADAS") != "0"
            or filtered.get("ARCHIVOS_ELIMINADOS") != "0"
        ):
            raise RuntimeError("Informe con permiso destructivo.")
        for key, value in filtered.items():
            print(f"{key}={value}")
        return process.returncode
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print("JELLYFIN_SESIONES_0021=BLOQUEADO")
        print("AUTORIZA_BORRADO_FISICO=NO")
        print("ARCHIVOS_ELIMINADOS=0")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
