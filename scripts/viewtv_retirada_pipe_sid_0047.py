"""0047: doble ensayo ACL de pipe Windows, solo sandbox; siempre BLOQUEADA."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker.retirement_pipe_sid_gate_0047 import (
    evaluar_pipe_0047,
)

SCRIPT = ROOT / "scripts" / "test_viewtv_windows_pipe_sid_sandbox_0047.ps1"


def _leer_windows_0047() -> str | None:
    """No acepta argumentos ni arranca el broker o WebUI reales."""
    distro = os.environ.get("WSL_DISTRO_NAME", "")
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", distro) is None:
        return None
    if SCRIPT.is_symlink() or not SCRIPT.is_file():
        return None
    # WSL UNC: fichero del proyecto, sin rutas arbitrarias ni PowerShell -Command.
    win_script = "\\\\wsl.localhost\\" + distro + str(SCRIPT).replace("/", "\\")
    try:
        run = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", win_script,
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
        if run.returncode != 0 or len(run.stdout) > 1000:
            return None
        return run.stdout
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    first, second = _leer_windows_0047(), _leer_windows_0047()
    result = evaluar_pipe_0047(first, second)
    print("PIPE_SIDS_0047=DOS_ENSAYOS_WIN32_SOLO_SANDBOX")
    print("ESTADO_RETIRADA_0047=BLOQUEADA")
    print("AUDITORIAS_VALIDAS=" + str(result["auditorias_validas"]))
    print("AUDITORIAS_EXIGIDAS=2")
    for reason in result["motivos"]:
        print("BARRERA_" + reason.upper() + "=PENDIENTE")
    print("BROKER_PRODUCTIVO_INSTALADO=NO")
    print("PERMISO_DE_BORRADO_OTORGADO=NO")
    print("ARCHIVOS_REALES_ELIMINADOS=0")
    print("TORRENTS_REALES_MODIFICADOS=0")
    # Nunca 0: 3 si auditado sin permiso, 2 si evidencia no verificable.
    return 3 if result["auditorias_validas"] == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
