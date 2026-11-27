"""Puerta local de mantenimiento del publicador: 100% solo lectura.

Desde WSL invoca la auditoría NTFS/Windows con PowerShell y procesa únicamente
un contrato de claves permitido. No imprime rutas, PIDs, usernames ni hashes.
No instala, no para tareas, no toca descargas o base de datos.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.publication_upgrade_gate_0023 import (
    InformeNoConfiable,
    evaluar_informe,
)

WINDOWS_SCRIPT = (
    "\\\\wsl.localhost\\Ubuntu-24.04"
    + str(ROOT / "scripts/viewtv_windows_publicador_upgrade_readonly_0023.ps1").replace(
        "/", "\\"
    )
)
ALLOWED_REASONS = frozenset({
    "tarea_no_deshabilitada",
    "privilegios_tarea_no_confiables",
    "accion_tarea_diferente",
    "wrapper_tarea_diferente",
    "publicador_instalado_desactualizado",
    "biblioteca_mutex_no_instalada",
    "biblioteca_mutex_version_diferente",
    "servicio_publicador_detectado",
    "servicio_publicador_activo",
    "procesos_publicador_observados",
    "procesos_no_inspeccionables",
    "instalacion_no_validada",
})


def main() -> int:
    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", WINDOWS_SCRIPT,
            ],
            text=True,
            capture_output=True,
            timeout=40,
            check=False,
        )
        if result.returncode != 0:
            raise InformeNoConfiable("Auditoría Windows falló.")
        report = evaluar_informe(result.stdout)
        if (
            report["permite_actualizar_automaticamente"] is not False
            or report["permite_eliminar_peliculas"] is not False
            or any(reason not in ALLOWED_REASONS for reason in report["bloqueos"])
        ):
            raise InformeNoConfiable("Resultado fuera de contrato.")
        print("UPGRADE_PUBLICADOR_0023=COMPROBADO_SOLO_LECTURA")
        print("BLOQUEOS_ACTUALES=" + str(len(report["bloqueos"])))
        for reason in report["bloqueos"]:
            print("BLOQUEO_" + reason.upper() + "=SI")
        print("REEMPLAZO_AUTOMATICO=NO")
        print("PUBLICADOR_PRODUCTIVO_MODIFICADO=NO")
        print("TAREAS_MODIFICADAS=0")
        print("MEDIOS_MODIFICADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        return 0
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError):
        print("UPGRADE_PUBLICADOR_0023=BLOQUEADO_FUENTE_NO_CONFIABLE")
        print("REEMPLAZO_AUTOMATICO=NO")
        print("MEDIOS_MODIFICADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
