"""Comprobación de lease 0013 SOLO sobre SQLite ficticia en /tmp.

NO otorga una capacidad firmada, no mueve ficheros y NO se usa en producción.
El broker real deberá revalidar el lease antes del movimiento con una autoridad
independiente; una lectura correcta puede caducar inmediatamente después.
"""

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from app.queue import _now

_MARKER = "VIEWTV_LEASE_GATE_SANDBOX_V1\n"
_ROOT_RE = re.compile(r"viewtv-lease-gate-[a-f0-9]{32}\Z")
_HASH_RE = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")


@dataclass(frozen=True)
class LeaseDecision:
    allowed: bool
    code: str


def _sandbox_db(path: Path) -> Path:
    """Aceptar exclusivamente <raíz marcada en /tmp>/organization.sqlite3."""
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("Ruta de prueba inválida.")
    root = path.parent
    if (
        path.name != "organization.sqlite3"
        or root.parent != Path("/tmp")
        or _ROOT_RE.fullmatch(root.name) is None
        or root.is_symlink()
        or not root.is_dir()
        or root.resolve() != root
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
    ):
        raise ValueError("SQLite fuera del sandbox permitido.")
    marker = root / ".viewtv-lease-gate-sandbox-only"
    if (
        marker.is_symlink()
        or not marker.is_file()
        or marker.read_text(encoding="utf-8") != _MARKER
    ):
        raise ValueError("Marcador de prueba inválido.")
    return path


def _read_expiration(value: object) -> datetime:
    """SQLModel/SQLite almacena timestamps UTC habitualmente sin tzinfo."""
    if not isinstance(value, str):
        raise ValueError("Vencimiento inválido.")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def check_sandbox_organization_lease(
    database: Path,
    download_id: int,
    worker_id: str,
    expected_attempt: int,
    expected_torrent_hash: str,
    *,
    now: datetime | None = None,
) -> LeaseDecision:
    """Solo lee SQLite. El intento evita ABA aun si vuelve el mismo worker."""
    if (
        isinstance(download_id, bool)
        or not isinstance(download_id, int)
        or download_id <= 0
        or not isinstance(worker_id, str)
        or not 1 <= len(worker_id) <= 128
        or not worker_id.strip()
        or isinstance(expected_attempt, bool)
        or not isinstance(expected_attempt, int)
        or not 1 <= expected_attempt <= 3
        or not isinstance(expected_torrent_hash, str)
        or _HASH_RE.fullmatch(expected_torrent_hash) is None
    ):
        return LeaseDecision(False, "identidad_invalida")
    try:
        current = _now(now)
        db = _sandbox_db(database)
        # Open a fresh read-only snapshot on every invocation; never use a
        # writable connection, an imported production engine or shared cache.
        uri = "file:" + quote(str(db), safe="/") + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=1.0)) as connection:
            connection.execute("PRAGMA query_only=ON")
            row = connection.execute(
                """
                SELECT estado, progreso, estado_verificacion, verificada_en,
                       qbittorrent_hash, organizacion_estado,
                       organizacion_locked_by, organizacion_locked_until,
                       organizacion_intentos
                  FROM descarga WHERE id = ? LIMIT 1
                """,
                (download_id,),
            ).fetchone()
    except (ValueError, OSError, sqlite3.Error):
        return LeaseDecision(False, "fuente_no_verificable")

    if row is None:
        return LeaseDecision(False, "sin_trabajo")
    (
        state, progress, verification, verified_at, torrent_hash,
        organization, owner, until, attempts,
    ) = row
    if (
        state != "completada"
        or progress != 1
        or verification != "verificada"
        or verified_at is None
        or organization != "pendiente"
        or owner != worker_id
        or attempts != expected_attempt
        or not isinstance(torrent_hash, str)
        or torrent_hash.lower() != expected_torrent_hash
    ):
        return LeaseDecision(False, "trabajo_o_identidad_no_vigente")
    try:
        expiration = _read_expiration(until)
    except (ValueError, TypeError, OverflowError):
        return LeaseDecision(False, "lease_no_vigente")
    if expiration <= current:
        return LeaseDecision(False, "lease_no_vigente")
    return LeaseDecision(True, "lease_vigente_en_consulta")
