"""Candidatas a revisión administrativa: todo GET, sin credenciales.

No produce aprobaciones firmadas, ni solicita PIN ni crea una clave.
No acepta rutas de borrado o IDs seleccionados desde argumentos.
Siempre informa que la eliminación permanece deshabilitada.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.viewtv_retirada_preflight_0018 import (  # noqa: E402
    _api_snapshot,
    _evidence_windows,
    _journals_readonly,
)
from worker.retirement_authorization_0019 import (  # noqa: E402
    AutorizacionDenegada,
    epoch_now,
    preparar_desafio_de_evidencias,
)
from worker.retirement_preflight_0018 import evaluar_retiradas  # noqa: E402


def main() -> int:
    try:
        before = _evidence_windows()
        snapshot = _api_snapshot()
        journals = _journals_readonly()
        after = _evidence_windows()
        if before != after:
            raise AutorizacionDenegada("Evidencias Windows cambiaron.")
        results = evaluar_retiradas(snapshot, journals, after)
        candidates = 0
        all_reasons = Counter()
        now = epoch_now()
        for row in results:
            all_reasons.update(row["motivos"])
            if row["motivos"] != ["falta_autorizacion_administrador"]:
                continue
            # Si el preflight no contiene descarga.id vinculado al mismo
            # medio no se emite ningún desafío. No se infiere por título.
            for download_id in sorted(journals):
                try:
                    challenge = preparar_desafio_de_evidencias(
                        snapshot, journals, after,
                        medio_id=row["medio_id"],
                        descarga_id=download_id, now=now,
                    )
                except AutorizacionDenegada:
                    continue
                if challenge["prueba_sha256"]:
                    candidates += 1
        print("ADMIN_PREFLIGHT_0019=SOLO_LECTURA")
        print("PELICULAS_ANALIZADAS=" + str(len(results)))
        print("CANDIDATAS_SIN_OTROS_BLOQUEOS=" + str(candidates))
        print("HAY_CLAVE_ADMINISTRATIVA_EN_API=NO")
        print("APROBACIONES_EMITIDAS=0")
        print("PERMISO_BORRADO_FISICO=NO")
        print("OPERACIONES_BORRADO_Y_QBIT=0")
        for reason, count in sorted(all_reasons.items()):
            print("BLOQUEO_" + reason.upper() + "=" + str(count))
        return 0
    except (AutorizacionDenegada, OSError, ValueError, RuntimeError, KeyError):
        print("ADMIN_PREFLIGHT_0019=BLOQUEADO")
        print("PERMISO_BORRADO_FISICO=NO")
        print("OPERACIONES_BORRADO_Y_QBIT=0")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
