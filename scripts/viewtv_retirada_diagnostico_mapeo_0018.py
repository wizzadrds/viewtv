"""Diagnóstico agregado de pertenencia de los archivos qBit al diario.

Se alimenta de GET de API / diario RO, NO imprime nombres, rutas o hashes.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.viewtv_retirada_preflight_0018 import _api_snapshot, _journals_readonly
from worker.retirement_preflight_0018 import _valid_relative


def main() -> None:
    snap = _api_snapshot()
    journals = _journals_readonly()
    counters = {
        "qbit_archivos": 0,
        "qbit_nombres_no_normalizables": 0,
        "qbit_archivos_con_correspondencia_exacta": 0,
        "qbit_archivos_extra_no_publicados": 0,
        "manifiesto_archivos": 0,
        "descargas_con_archivos_extra": 0,
    }
    for download in snap.get("descargas", []):
        id_ = download.get("id")
        journal = journals.get(id_)
        if journal is None:
            continue
        files = journal[0].get("intent", {}).get("files", [])
        names = {
            f.get("source_relative", "").casefold()
            for f in files
            if isinstance(f, dict)
            and isinstance(f.get("source_relative"), str)
        }
        counters["manifiesto_archivos"] += len(names)
        actual = snap.get("qbittorrent", {}).get(str(id_), {}).get("files", [])
        extra = 0
        for f in actual:
            counters["qbit_archivos"] += 1
            name = f.get("name") if isinstance(f, dict) else ""
            normalized = name.replace("\\", "/") if isinstance(name, str) else ""
            if _valid_relative(normalized) is None:
                counters["qbit_nombres_no_normalizables"] += 1
            if normalized.casefold() in names:
                counters["qbit_archivos_con_correspondencia_exacta"] += 1
            else:
                counters["qbit_archivos_extra_no_publicados"] += 1
                extra += 1
        if extra:
            counters["descargas_con_archivos_extra"] += 1
    for key, value in counters.items():
        print("MAPEO_" + key.upper() + "=" + str(value))
    print("RUTAS_NOMBRES_Y_HASHES_IMPRESOS=0")
    print("OPERACIONES_DE_ESCRITURA=0")


if __name__ == "__main__":
    main()
