"""0052: doble verificación del broker Windows instalado sin arrancarlo."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker.retirement_installed_broker_gate_0052 import (
    evaluar_servicio_0052,
)

TARGET = ROOT / "scripts" / "viewtv_windows_broker_verify_readonly_0052.ps1"


def _leer_host_0052() -> str | None:
    distro = os.environ.get("WSL_DISTRO_NAME", "")
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", distro) is None:
        return None
    if not TARGET.is_file() or TARGET.is_symlink():
        return None
    path = "\\\\wsl.localhost\\" + distro + str(TARGET).replace("/", "\\")
    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", path,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="ascii",
            errors="strict",
            check=False,
            timeout=25,
            cwd=ROOT,
        )
        if result.returncode != 0 or len(result.stdout) > 850:
            return None
        return result.stdout
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    reports = (_leer_host_0052(), _leer_host_0052())
    status = evaluar_servicio_0052(*reports)
    print("BROKER_WINDOWS_0052=SID_SERVICIO_INERTE_INSTALADO")
    print("ESTADO_RETIRADA_0052=BLOQUEADA")
    print("AUDITORIAS_VALIDAS=" + str(status["auditorias_validas"]))
    print("AUDITORIAS_EXIGIDAS=2")
    for reason in status["motivos"]:
        print("BARRERA_" + reason.upper() + "=PENDIENTE")
    print("BROKER_FISICO_CON_ELIMINACION_INSTALADO=NO")
    print("PERMISO_DE_BORRADO_OTORGADO=NO")
    print("ARCHIVOS_REALES_ELIMINADOS=0")
    print("TORRENTS_REALES_MODIFICADOS=0")
    return 3 if status["auditorias_validas"] == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
