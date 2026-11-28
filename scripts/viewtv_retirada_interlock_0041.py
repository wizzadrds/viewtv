"""0041: único preflight agregado de siete auditorías VIEWTV, SOLO LECTURA.

Ejecuta scripts de nombre fijo; sin rutas, títulos, hashes, secretos ni
parámetros. Acota tiempo, código y salida de cada proceso; NO hace ninguna
operación de qBit POST, Jellyfin write, Windows ACL, unlink o SQL write.
Siempre termina BLOQUEADA incluso con 8 reportes aparentemente perfectos.
"""
from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker.retirement_unified_gate_0041 import (
    SOURCES,
    evaluar_interlock_0041,
    parsear_fuente_0041,
)

FILES = {
    "0018": "viewtv_retirada_preflight_0018.py",
    "0019": "viewtv_retirada_admin_preflight_0019.py",
    "0026": "viewtv_retirada_custodia_qbit_0026.py",
    "0027": "viewtv_retirada_superficie_reproduccion_0027.py",
    "0033": "viewtv_retirada_accesos_gate_0033.py",
    "0037": "viewtv_retirada_sids_gate_0037.py",
    "0040": "viewtv_retirada_webui_qbit_0040.py",
}
TIMEOUT = {
    "0018": 105, "0019": 105, "0026": 115, "0027": 30,
    "0033": 120, "0037": 120, "0040": 155,
}


def _read_only(source: str) -> str | None:
    """Timeout y código verificados; jamás transmitir stderr al usuario."""
    if source not in FILES:
        return None
    file = ROOT / "scripts" / FILES[source]
    if not file.is_file() or file.is_symlink():
        return None
    try:
        result = subprocess.run(
            [sys.executable, "-B", str(file)],
            capture_output=True,
            text=True,
            check=False,
            timeout=TIMEOUT[source],
            cwd=ROOT,
        )
        if result.returncode != 0 or not 80 <= len(result.stdout) <= 16384:
            return None
        return result.stdout.strip()
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    reports: dict[str, str | None] = {}
    # La segunda lectura del preflight físico cierra el intervalo global.
    reports["0018_inicial"] = _read_only("0018")
    sources = ("0019", "0026", "0027", "0033", "0037", "0040")
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = dict(zip(sources, pool.map(_read_only, sources), strict=True))
    reports.update(results)
    reports["0018_final"] = _read_only("0018")
    decision = evaluar_interlock_0041(reports)
    if (
        decision["estado"] != "bloqueada"
        or decision["puede_retirar_archivos"] is not False
        or decision["permiso_de_borrado_otorgado"] is not False
    ):
        print("INTERLOCK_0041=INFORME_NO_CONFIABLE")
        print("ESTADO_RETIRADA_0041=BLOQUEADA")
        print("PERMISO_DE_BORRADO_OTORGADO=NO")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        return 2
    print("INTERLOCK_0041=SIETE_FUENTES_SOLO_LECTURA")
    print("ESTADO_RETIRADA_0041=BLOQUEADA")
    for key in SOURCES:
        report = reports.get(key)
        try:
            if report is None:
                raise ValueError("Fuente no disponible.")
            parsear_fuente_0041(key.split("_", 1)[0], report)
            print("FUENTE_" + key.upper() + "=VALIDADA_NO_AUTORIZADORA")
        except (ValueError, TypeError, KeyError):
            print("FUENTE_" + key.upper() + "=NO_VERIFICABLE")
    for reason in decision["motivos"]:
        print("BARRERA_" + reason.upper() + "=PENDIENTE")
    print("FUENTES_VERIFICADAS=" + str(decision["fuentes_verificadas"]))
    print("FUENTES_EXIGIDAS=" + str(decision["fuentes_exigidas"]))
    print("PERMISO_DE_BORRADO_OTORGADO=NO")
    print("ARCHIVOS_ELIMINADOS=0")
    print("TORRENTS_MODIFICADOS=0")
    evidence_invalid = any(
        reason.startswith((
            "fuente_", "inventario_", "preflight_0018_cambio",
            "recuento_de_peliculas", "diarios_ntfs_no_cubiertos",
        ))
        for reason in decision["motivos"]
    )
    # EXPLICITO: 3 = informes coherentes pero retirada BLOQUEADA;
    # 2 = evidencia inconsistente. JAMAS codigo cero (no autorizador).
    if evidence_invalid or decision["fuentes_verificadas"] != len(SOURCES):
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
