"""Revisión local por película y año, nunca autoriza retirada ni escribe.

Ejemplo: python3 scripts/viewtv_retirada_revision_solicitud_0024.py
              --titulo "Ejemplo" --anio 2026
El título se transmite solo al proceso Python de la API; la salida
omite nombres, IDs de perfiles, hashes, rutas, tokens y películas ajenas.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from viewtv_retirada_preflight_0018 import (
    _api_snapshot,
    _evidence_windows,
    _journals_readonly,
)

from worker.retirement_evidence_stability_0025 import (
    EvidenciaInestable,
    certificar_doble_lectura,
)
from worker.retirement_preflight_0018 import evaluar_retiradas
from worker.retirement_request_review_0024 import (
    RevisionNoConfiable,
    resumir_revision,
)


def _detalle_api(titulo: str, anio: int) -> dict:
    source = (ROOT / "scripts/viewtv_retirada_solicitud_api_0024.py").read_text(
        encoding="utf-8",
    )
    try:
        response = subprocess.run(
            [
                "docker", "exec", "-i", "viewtv-api-1", "python", "-",
                titulo, str(anio),
            ],
            input=source,
            capture_output=True, check=False, text=True, timeout=35,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RevisionNoConfiable("Fuente de revisión no disponible.") from exc
    if response.returncode != 0 or len(response.stdout) > 8192:
        raise RevisionNoConfiable("La fuente de revisión no responde.")
    try:
        result = json.loads(response.stdout)
    except ValueError as exc:
        raise RevisionNoConfiable("La fuente no emitió JSON validado.") from exc
    if not isinstance(result, dict):
        raise RevisionNoConfiable("Detalle no verificable.")
    return result


def revisar(titulo: str, anio: int) -> dict:
    if not isinstance(titulo, str) or not 1 <= len(titulo) <= 500:
        raise RevisionNoConfiable("Título no válido.")
    if type(anio) is not int or not 1870 <= anio <= 2200:
        raise RevisionNoConfiable("Año no válido.")

    first_windows = _evidence_windows()
    first_detail = _detalle_api(titulo, anio)
    first_snapshot = _api_snapshot()
    first_journals = _journals_readonly()
    # La consulta completa Jellyfin + qBit no es atómica.
    # Dos fotografías sirven para detectar drift; NO congelan los servicios.
    last_snapshot = _api_snapshot()
    last_journals = _journals_readonly()
    last_detail = _detalle_api(titulo, anio)
    last_windows = _evidence_windows()
    if first_detail != last_detail:
        raise RevisionNoConfiable("La petición cambió durante la consulta.")
    try:
        certificar_doble_lectura(
            first_snapshot, last_snapshot,
            first_journals, last_journals,
            first_windows, last_windows,
        )
    except EvidenciaInestable as exc:
        raise RevisionNoConfiable(
            "Evidencias de la película cambiaron entre consultas."
        ) from exc

    rows = evaluar_retiradas(last_snapshot, last_journals, last_windows)
    result = resumir_revision(last_snapshot, rows, last_detail)
    if result["autoriza_borrado_fisico"] is not False:
        raise RevisionNoConfiable("Preflight devolvió permiso inesperado.")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Revisión de película con petición, exclusivamente lectura.",
    )
    parser.add_argument("--titulo", required=True)
    parser.add_argument("--anio", required=True, type=int)
    args = parser.parse_args(argv)

    try:
        info = revisar(args.titulo, args.anio)
    except (OSError, RuntimeError, KeyError, TypeError, ValueError):
        print("REVISION_SOLICITUD_0024=BLOQUEADA_DATOS_NO_CONFIABLES")
        print("APROBACION_ADMINISTRATIVA_EMITIDA=NO")
        print("PERMISO_BORRADO_FISICO=NO")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        return 2
    print("REVISION_SOLICITUD_0024=SOLO_LECTURA")
    print("ESTADO=" + info["estado"].upper())
    print("DOBLE_SNAPSHOT_SQL_JELLYFIN_QBIT=COINCIDENTE")
    print("DOBLE_INVENTARIO_DIARIOS_NTFS=COINCIDENTE")
    print("EXCLUSION_TRANSACCIONAL_QBIT_JELLYFIN=NO")
    print("MEDIO_ID=" + str(info["medio_id"]))
    print("PERFILES_ACTIVOS=" + str(info["perfiles_activos"]))
    print("PERFILES_CON_VISTO=" + str(info["perfiles_con_visto"]))
    print("PERFILES_SIN_VISTO=" + str(info["perfiles_sin_visto"]))
    print("SOLICITUDES_PENDIENTES=" + str(info["solicitudes_pendientes"]))
    print("SOLICITUD_VALIDA_REGISTRADA=" + (
        "SI" if info["solicitud_valida_registrada"] else "NO"
    ))
    print("VISTA_EN_TODOS_LOS_PERFILES=" + (
        "SI" if info["vista_en_todos_los_perfiles"] else "NO"
    ))
    for reason in info["bloqueos"]:
        print("BLOQUEO_" + reason.upper() + "=SI")
    print("APROBACION_ADMINISTRATIVA_EMITIDA=NO")
    print("PERMISO_BORRADO_FISICO=NO")
    print("ARCHIVOS_ELIMINADOS=0")
    print("TORRENTS_MODIFICADOS=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
