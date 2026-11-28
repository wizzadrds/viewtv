"""VIEWTV 0037: doble auditoría Windows de identidades, SIEMPRE BLOQUEANTE.

Sin películas, rutas de usuario o secretos como argumentos. No modifica
Windows, SQLite, ACL, Jellyfin ni qBittorrent; sólo lee indicadores.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.retirement_sid_gate_0037 import evaluar_aislamiento_sids_0037

WINDOWS_AUDIT = ROOT / "scripts" / "viewtv_windows_sids_acl_readonly_0037.ps1"


def _observar_windows() -> str:
    if not WINDOWS_AUDIT.is_file() or WINDOWS_AUDIT.is_symlink():
        raise RuntimeError("Auditoría SIDs no disponible.")
    ps_file = "\\\\wsl.localhost\\Ubuntu-24.04" + str(WINDOWS_AUDIT).replace("/", "\\")
    run = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", ps_file,
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if run.returncode != 0 or not 75 <= len(run.stdout) <= 2048:
        raise RuntimeError("Windows no devolvió evidencias verificables.")
    return run.stdout.strip()


def main() -> int:
    try:
        first = _observar_windows()
        second = _observar_windows()
        decision = evaluar_aislamiento_sids_0037(first, second)
        if decision["permiso_de_borrado_otorgado"] is not False:
            raise RuntimeError("La auditoría no puede conceder permisos.")
        print("RETIRADA_SIDS_0037=AUDITORIA_REAL_SOLO_LECTURA")
        print("ESTADO_RETIRADA_0037=BLOQUEADA")
        for issue in decision["motivos"]:
            print("BARRERA_" + issue.upper() + "=PENDIENTE")
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
        print("RETIRADA_SIDS_0037=EVIDENCIA_INCOMPLETA")
        print("ESTADO_RETIRADA_0037=BLOQUEADA")
        return 2
    finally:
        print("PERMISO_DE_BORRADO_OTORGADO=NO")
        print("ARCHIVOS_REALES_ELIMINADOS=0")
        print("TORRENTS_REALES_MODIFICADOS=0")


if __name__ == "__main__":
    raise SystemExit(main())
