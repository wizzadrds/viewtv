"""0049: dos muertes Windows en sandbox GUID; nunca devuelve éxito 0."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker.retirement_nonce_durable_gate_0049 import (
    evaluar_nonce_0049,
)

TARGET = ROOT / "scripts" / "test_viewtv_windows_pipe_nonce_durable_sandbox_0049.ps1"


def _observar_0049() -> str | None:
    distro = os.environ.get("WSL_DISTRO_NAME", "")
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", distro) is None:
        return None
    if TARGET.is_symlink() or not TARGET.is_file():
        return None
    native_script = "\\\\wsl.localhost\\" + distro + str(TARGET).replace("/", "\\")
    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", native_script,
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
        if result.returncode or len(result.stdout) > 1400:
            return None
        return result.stdout
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    reports = (_observar_0049(), _observar_0049())
    verdict = evaluar_nonce_0049(*reports)
    print("NONCE_REPLAY_WINDOWS_0049=SOLO_SANDBOX")
    print("ESTADO_RETIRADA_0049=BLOQUEADA")
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
