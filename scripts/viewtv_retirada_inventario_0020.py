"""Inventario qBit en producción SOLO GET, sin nombres ni rutas en salida.

La clasificación nunca habilita borrados. Lee diarios privados desde WSL.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.viewtv_retirada_preflight_0018 import _api_snapshot, _journals_readonly
from worker.retirement_inventory_0020 import analizar_inventario


def main() -> int:
    try:
        snapshot = _api_snapshot()
        journals = _journals_readonly()
        summary = analizar_inventario(snapshot, journals)
        if summary["qbit_no_disponible"] != 0:
            raise ValueError("Hay inventarios sin verificar.")
        print("INVENTARIO_0020=SOLO_LECTURA")
        for key, value in sorted(summary.items()):
            print(key.upper() + "=" + str(value))
        print("TAMANO_LOGICO_NO_ES_ESPACIO_LIBERABLE=SI")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, TypeError):
        print("INVENTARIO_0020=BLOQUEADO")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
