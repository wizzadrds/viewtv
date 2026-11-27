"""0026: dos GET qBit/Jellyfin completos y custodia de todos sus archivos.

Solo lectura; no solicita cambios de estado, ni pausa torrents, ni borra.
No imprime nombres, hash, perfiles, títulos, rutas, ni IDs de descarga.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from viewtv_retirada_preflight_0018 import (  # noqa: E402
    _api_snapshot,
    _evidence_windows,
    _journals_readonly,
)
from worker.retirement_evidence_stability_0025 import (  # noqa: E402
    certificar_doble_lectura,
)
from worker.retirement_qbit_custody_0026 import (  # noqa: E402
    evaluar_custodia_qbit,
)

COUNTERS = (
    "descargas",
    "torrent_completo_y_en_reposo_reportado",
    "torrent_no_en_reposo_o_incompleto",
    "torrent_propiedad_o_ruta_inconsistente",
    "torrents_con_archivos_extra",
    "archivos_qbit",
    "archivos_publicados_correlacionados",
    "archivos_extra_protegidos",
    "extras_con_nombre_no_normalizable",
    "extras_tipo_video",
    "extras_tipo_subtitulo",
    "extras_tipo_metadato",
    "extras_tipo_otro",
    "bytes_logicos_extras_protegidos",
    "archivos_con_tamano_incompatible",
    "archivos_con_progreso_incompleto",
    "archivos_con_prioridad_excluida",
)


def custodia() -> dict:
    first_ntfs = _evidence_windows()
    first_snap = _api_snapshot()
    first_journals = _journals_readonly()
    last_snap = _api_snapshot()
    last_journals = _journals_readonly()
    last_ntfs = _evidence_windows()
    certificar_doble_lectura(
        first_snap, last_snap,
        first_journals, last_journals,
        first_ntfs, last_ntfs,
    )
    return evaluar_custodia_qbit(last_snap, last_journals)


def main() -> int:
    try:
        result = custodia()
        if (
            result["autoriza_borrado_fisico"] is not False
            or result["bloqueo_jellyfin_y_qbit_transaccional"] is not False
            or result["archivos_eliminados"] != 0
            or result["torrents_modificados"] != 0
        ):
            raise ValueError("Resultado de custodia fuera de contrato.")
        print("CUSTODIA_QBIT_0026=SOLO_GET")
        print("DOBLE_SNAPSHOT_SQL_JELLYFIN_QBIT=COINCIDENTE")
        print("DOBLE_EVIDENCIA_DIARIOS_Y_NTFS=COINCIDENTE")
        for key in COUNTERS:
            print(key.upper() + "=" + str(result[key]))
        print("BYTES_LOGICOS_EXTRAS_NO_SON_ESPACIO_RECUPERABLE=SI")
        print("EXTRAS_CONSERVADOS=SI")
        print("QUIETUD_TRANSACCIONAL_QBIT_JELLYFIN=NO")
        print("PERMISO_BORRADO_FISICO=NO")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        return 0
    except (OSError, RuntimeError, KeyError, TypeError, ValueError):
        print("CUSTODIA_QBIT_0026=BLOQUEADA_FUENTE_NO_CONFIABLE")
        print("PERMISO_BORRADO_FISICO=NO")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
