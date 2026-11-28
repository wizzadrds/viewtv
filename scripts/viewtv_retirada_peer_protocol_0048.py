"""0048: dos verificaciones Win32 de peer identity; nunca código 0."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker.retirement_peer_protocol_gate_0048 import (
    evaluar_protocolo_pipe_0048,
)

TARGET = ROOT / "scripts" / "test_viewtv_windows_pipe_peer_protocol_sandbox_0048.ps1"


def _observar_0048() -> str | None:
    distro = os.environ.get("WSL_DISTRO_NAME", "")
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", distro) is None:
        return None
    if not TARGET.is_file() or TARGET.is_symlink():
        return None
    win_path = "\\\\wsl.localhost\\" + distro + str(TARGET).replace("/", "\\")
    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", win_path,
            ],
            capture_output=True,
            text=True,
            encoding="ascii",
            errors="strict",
            stdin=subprocess.DEVNULL,
            check=False,
            timeout=25,
            cwd=ROOT,
        )
        if result.returncode != 0 or len(result.stdout) > 1200:
            return None
        return result.stdout
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    evidence = (_observar_0048(), _observar_0048())
    result = evaluar_protocolo_pipe_0048(*evidence)
    print("PROTOCOLO_PEER_WINDOWS_0048=SOLO_SANDBOX")
    print("ESTADO_RETIRADA_0048=BLOQUEADA")
    print("AUDITORIAS_VALIDAS=" + str(result["auditorias_validas"]))
    print("AUDITORIAS_EXIGIDAS=2")
    for reason in result["motivos"]:
        print("BARRERA_" + reason.upper() + "=PENDIENTE")
    print("BROKER_PRODUCTIVO_INSTALADO=NO")
    print("PERMISO_DE_BORRADO_OTORGADO=NO")
    print("ARCHIVOS_REALES_ELIMINADOS=0")
    print("TORRENTS_REALES_MODIFICADOS=0")
    # 3: pruebas válidas pero bloqueo; 2: fuente o contrato falla.
    return 3 if result["auditorias_validas"] == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
