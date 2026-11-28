"""0051: inventario real SOLO LECTURA y plan de migración sin ejecución.

Consume dos auditorías Win32 por 0033/0037/0040; imprime solo clases
de riesgo, jamás SID, IP, claves, contraseñas, rutas de películas o hashes.
Siempre código no cero; jamás permiso de borrado ni cambio de host.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker.retirement_migration_plan_0051 import (
    SOURCES,
    planificar_aislamiento_0051,
)

WIN_SCRIPTS = {
    "0033": "viewtv_windows_accesos_externos_readonly_0033.ps1",
    "0037": "viewtv_windows_sids_acl_readonly_0037.ps1",
    "0040": "viewtv_windows_qbit_webui_readonly_0040.ps1",
}
LIMITS = {"0033": 4096, "0037": 2048, "0040": 2048}


def _audit(name: str) -> str | None:
    if name not in SOURCES:
        return None
    distro = os.environ.get("WSL_DISTRO_NAME", "")
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", distro) is None:
        return None
    target = ROOT / "scripts" / WIN_SCRIPTS[name]
    if not target.is_file() or target.is_symlink():
        return None
    win_path = "\\\\wsl.localhost\\" + distro + str(target).replace("/", "\\")
    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", win_path,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="ascii",
            errors="strict",
            check=False,
            timeout=90,
            cwd=ROOT,
        )
        if result.returncode or not 75 <= len(result.stdout) <= LIMITS[name]:
            return None
        return result.stdout.replace("\r\n", "\n").strip()
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    reports = {name: (_audit(name), _audit(name)) for name in SOURCES}
    decision = planificar_aislamiento_0051(reports)
    print("AISLAMIENTO_0051=PLAN_DE_MIGRACION_SOLO_LECTURA")
    print("ESTADO_RETIRADA_0051=BLOQUEADA")
    print("FUENTES_VALIDAS=" + str(decision["fuentes_validas"]))
    print("FUENTES_EXIGIDAS=3")
    print("VENTANA_MANTENIMIENTO_AUTORIZADA=NO")
    for index, phase in enumerate(decision["fases"], 1):
        print(f"FASE_{index:02d}={phase.upper()}_PENDIENTE")
    for reason in decision["motivos"]:
        print("BARRERA_" + reason.upper() + "=PENDIENTE")
    print("BROKER_PRODUCTIVO_INSTALADO=NO")
    print("PERMISO_DE_BORRADO_OTORGADO=NO")
    print("ARCHIVOS_REALES_ELIMINADOS=0")
    print("TORRENTS_REALES_MODIFICADOS=0")
    return 3 if decision["inventario_completo"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
