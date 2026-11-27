"""Diagnóstico SOLO lectura de tres rutas de reproducción + puerto Docker.

Nunca inserta una barrera en producción ni modifica configuración o sesión.
No imprime rutas, claves, información de redes ajenas ni URLs firmadas.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.retirement_playback_surface_0027 import (  # noqa: E402
    auditar_superficie,
)


def comprobar() -> dict:
    playback = (ROOT / "backend/app/jellyfin_playback.py").read_text(
        encoding="utf-8"
    )
    hls = (ROOT / "backend/app/jellyfin_hls.py").read_text(
        encoding="utf-8"
    )
    result = auditar_superficie(playback, hls)
    output = subprocess.run(
        ["docker", "port", "viewtv-jellyfin"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if output.returncode != 0 or len(output.stdout) > 2000:
        raise ValueError("Publicación Jellyfin no verificable.")
    lines = output.stdout.strip().splitlines()
    parsed = [
        re.fullmatch(r"8096/tcp -> (127\.0\.0\.1|\[::1\]):[0-9]{1,5}", line)
        for line in lines
    ]
    if not lines or any(item is None for item in parsed):
        raise ValueError("Puerto Docker Jellyfin inesperado.")
    result["puerto_publicado_solo_loopback"] = True
    return result


def main() -> int:
    try:
        report = comprobar()
        if (
            report["autoriza_retirada_fisica"] is not False
            or report["control_admision_productivo_0027_instalado"] is not False
            or report["streams_jellyfin_directos_fuera_de_viewtv_excluidos"] is not False
        ):
            raise ValueError("Auditoría no conservadora.")
        print("SUPERFICIE_PLAYBACK_0027=SOLO_LECTURA")
        print("RUTAS_AUTENTICADAS_CONTADAS=" + str(report["rutas_verificadas"]))
        print("TTL_HLS_SEGUNDOS=" + str(report["ttl_hls_segundos"]))
        print("PUERTO_JELLYFIN_PUBLICADO_SOLO_LOOPBACK=SI")
        print("OTROS_ACCESOS_JELLYFIN_DESCARTADOS=NO")
        print("PROTOCOLO_ADMISION_0027_INSTALADO=NO")
        print("BLOQUEO_REAL_DE_NUEVOS_STREAMS=NO")
        print("PERMISO_BORRADO_FISICO=NO")
        print("SERVICIOS_MODIFICADOS=0")
        print("REPRODUCCIONES_MODIFICADAS=0")
        return 0
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        print("SUPERFICIE_PLAYBACK_0027=BLOQUEADA_DATOS_NO_CONFIABLES")
        print("PROTOCOLO_ADMISION_0027_INSTALADO=NO")
        print("PERMISO_BORRADO_FISICO=NO")
        print("SERVICIOS_MODIFICADOS=0")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
