"""VIEWTV 0040: dos consultas Windows de WebUI/GUI qBit, NUNCA autoriza.

Sin parámetros y sin claves: observa procesos, sockets, reglas y presencia
de opciones locales. No contacta WebUI, no detiene ni reanuda torrents.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.retirement_qbit_webui_gate_0040 import (
    evaluar_webui_qbit_0040,
)

AUDIT = ROOT / "scripts" / "viewtv_windows_qbit_webui_readonly_0040.ps1"


def _audit_windows() -> str:
    if not AUDIT.is_file() or AUDIT.is_symlink():
        raise RuntimeError("Auditoría nativa inexistente o redirigida.")
    path = "\\\\wsl.localhost\\Ubuntu-24.04" + str(AUDIT).replace("/", "\\")
    result = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", path,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=65,
    )
    if result.returncode != 0 or not 90 <= len(result.stdout) <= 2048:
        raise RuntimeError("Auditoría Windows no verificable.")
    return result.stdout.strip()


def main() -> int:
    try:
        previous = _audit_windows()
        current = _audit_windows()
        verdict = evaluar_webui_qbit_0040(previous, current)
        if (
            verdict["estado"] != "bloqueada"
            or verdict["permiso_de_borrado_otorgado"] is not False
        ):
            raise RuntimeError("No está permitido autorizar desde auditoría.")
        print("RETIRADA_WEBUI_QBIT_0040=AUDITORIA_REAL_SOLO_LECTURA")
        print("ESTADO_RETIRADA_0040=BLOQUEADA")
        for issue in verdict["motivos"]:
            print("BARRERA_" + issue.upper() + "=PENDIENTE")
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
        print("RETIRADA_WEBUI_QBIT_0040=EVIDENCIA_INCOMPLETA")
        print("ESTADO_RETIRADA_0040=BLOQUEADA")
        return 2
    finally:
        print("PERMISO_DE_BORRADO_OTORGADO=NO")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")


if __name__ == "__main__":
    raise SystemExit(main())
