"""0050: doble ensayo Win32 peer + journal; siempre BLOQUEADA."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker.retirement_pipe_nonce_gate_0050 import (
    evaluar_peer_nonce_0050,
)

TARGET = ROOT / "scripts" / "test_viewtv_windows_pipe_peer_nonce_sandbox_0050.ps1"


def _observar_0050() -> str | None:
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
            timeout=45,
            cwd=ROOT,
        )
        if result.returncode != 0 or len(result.stdout) > 1400:
            return None
        return result.stdout
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    reports = (_observar_0050(), _observar_0050())
    verdict = evaluar_peer_nonce_0050(*reports)
    print("PIPE_PEER_Y_NONCE_DURABLE_0050=SOLO_SANDBOX")
    print("ESTADO_RETIRADA_0050=BLOQUEADA")
    print("AUDITORIAS_VALIDAS=" + str(verdict["auditorias_validas"]))
    print("AUDITORIAS_EXIGIDAS=2")
    for reason in verdict["motivos"]:
        print("BARRERA_" + reason.upper() + "=PENDIENTE")
    print("BROKER_PRODUCTIVO_INSTALADO=NO")
    print("PERMISO_DE_BORRADO_OTORGADO=NO")
    print("ARCHIVOS_REALES_ELIMINADOS=0")
    print("TORRENTS_REALES_MODIFICADOS=0")
    return 3 if verdict["auditorias_validas"] == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
