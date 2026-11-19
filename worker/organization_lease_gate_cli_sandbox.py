"""Interfaz CLI de SOLO LECTURA para probar el lease de una SQLite ficticia.

No autentica peticiones: la autorización de producción necesita un servicio
independiente, identidades separadas y revalidación justo antes de mover.
"""

import argparse
import json
from pathlib import Path

from app.organization_publication_gate_sandbox import (
    check_sandbox_organization_lease,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Comprobación solo sandbox 0013")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--download-id", required=True, type=int)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--torrent-hash", required=True)
    args = parser.parse_args()
    result = check_sandbox_organization_lease(
        args.database,
        args.download_id,
        args.worker_id,
        args.attempt,
        args.torrent_hash,
    )
    print(json.dumps(
        {"allowed": result.allowed, "code": result.code},
        separators=(",", ":"),
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
