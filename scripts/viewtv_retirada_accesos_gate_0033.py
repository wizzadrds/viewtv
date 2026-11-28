"""0033: dos auditorías Windows SOLO LECTURA y decisión fail-closed.

No acepta películas, rutas, credenciales o comandos desde la línea de
órdenes. No es preflight autorizador ni modifica Windows, Docker o torrents.
Las constataciones de red NO prueban exclusividad kernel de los archivos.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.retirement_external_gate_0033 import (
    evaluar_accesos_externos_0033,
)

AUDIT = ROOT / "scripts" / "viewtv_windows_accesos_externos_readonly_0033.ps1"


def _leer_auditoria() -> str:
    if not AUDIT.is_file() or AUDIT.is_symlink():
        raise RuntimeError("Auditoría no disponible.")
    ps_path = "\\\\wsl.localhost\\Ubuntu-24.04" + str(AUDIT).replace("/", "\\")
    result = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", ps_path,
        ],
        capture_output=True, text=True, check=False, timeout=45,
    )
    if result.returncode != 0 or not 80 <= len(result.stdout) <= 4096:
        raise RuntimeError("Auditoría nativa incompleta.")
    return result.stdout.strip()


def main() -> int:
    try:
        anterior = _leer_auditoria()
        posterior = _leer_auditoria()
        decision = evaluar_accesos_externos_0033(anterior, posterior)
        print("RETIRADA_ACCESOS_0033=AUDITORIA_REAL_SOLO_LECTURA")
        print("ESTADO_RETIRADA_0033=BLOQUEADA")
        print("PERMISO_DE_BORRADO_OTORGADO=NO")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        for motivo in decision["motivos"]:
            print("BARRERA_" + motivo.upper() + "=PENDIENTE")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print("RETIRADA_ACCESOS_0033=EVIDENCIA_INCOMPLETA")
        print("ESTADO_RETIRADA_0033=BLOQUEADA")
        print("PERMISO_DE_BORRADO_OTORGADO=NO")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
