"""Autorización independiente para futuras retiradas: SIN ejecutor de borrado.

Contrato criptográfico: aprobación offline con clave del administrador host,
desafío ligado a prueba actual, expiración corta y consumo único en SQLite
privada. Nunca interpreta PINs de perfiles ni acepta aprobación desde la web.
No modifica películas, torrents, Jellyfin ni la SQLite de la API.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VERSION = 1
ACCION = "viewtv-retirada-pelicula"
REASON_ADMIN = "falta_autorizacion_administrador"
EXPIRE_SECONDS = 600
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
NONCE = re.compile(r"[a-f0-9]{32}\Z")
EXPECTED_FIELDS = frozenset({
    "version", "accion", "medio_id", "descarga_id", "prueba_sha256",
    "vence_epoch", "nonce",
})
MAX_DOC_BYTES = 2048


class AutorizacionDenegada(ValueError):
    """Cualquier ambigüedad cierra la aprobación, sin detalles secretos."""


def _int_positive(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _canonical(document: dict, max_bytes: int = MAX_DOC_BYTES) -> bytes:
    if not isinstance(document, dict):
        raise AutorizacionDenegada("Documento no reconocido.")
    try:
        result = json.dumps(
            document, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise AutorizacionDenegada("Documento no serializable.") from exc
    if len(result) > max_bytes:
        raise AutorizacionDenegada("Documento demasiado grande.")
    return result


def huella_evidencias_completas(
    snapshot: dict,
    journals: dict,
    ntfs: list[dict],
    *,
    medio_id: int,
    descarga_id: int,
) -> str:
    """La firma se vincula a TODO el preflight observado, no a un ID suelto.

    Todos los bloqueos menos la falta de administrador deben haberse
    resuelto; cualquier discrepancia de descargas/diarios cancela.
    Al reevaluar se debe recuperar la evidencia de todas las fuentes.
    """
    from worker.retirement_preflight_0018 import evaluar_retiradas

    if not _int_positive(medio_id) or not _int_positive(descarga_id):
        raise AutorizacionDenegada("Identidad de retirada inválida.")
    rows = evaluar_retiradas(snapshot, journals, ntfs)
    matches = [
        row for row in rows if row["medio_id"] == medio_id
        and row["estado"] == "bloqueada"
        and row["puede_borrarse_ahora"] is False
        and row["motivos"] == [REASON_ADMIN]
    ]
    if len(matches) != 1:
        raise AutorizacionDenegada("Preflight con otros bloqueos.")
    if descarga_id not in journals:
        raise AutorizacionDenegada("Diario de descarga ausente.")
    record, digest = journals[descarga_id]
    if (
        not isinstance(record, dict)
        or not isinstance(digest, str)
        or SHA256.fullmatch(digest) is None
        or record.get("download_id") != descarga_id
    ):
        raise AutorizacionDenegada("Diario de descarga no verificable.")
    downloads = snapshot.get("descargas", [])
    evidence = [
        row for row in ntfs if isinstance(row, dict)
        and row.get("download_id") == descarga_id
        and row.get("ntfs_verified") is True
        and row.get("journal_sha256") == digest
    ]
    if len(evidence) != 1 or sum(
        isinstance(row, dict) and row.get("id") == descarga_id
        for row in downloads
    ) != 1:
        raise AutorizacionDenegada("Propiedad de descarga no única.")
    # Vincular también la descarga concreta con la ruta Jellyfin
    # seleccionada para la película, sin considerar títulos.
    movies = [
        movie for movie in snapshot.get("peliculas", [])
        if isinstance(movie, dict) and movie.get("medio_id") == medio_id
    ]
    if len(movies) != 1:
        raise AutorizacionDenegada("Identidad de película no única.")
    paths = [
        item.get("path") for item in snapshot.get("jellyfin", {}).get("elementos", [])
        if isinstance(item, dict) and item.get("id") == movies[0].get("jellyfin_id")
        and item.get("tipo") == "Movie"
    ]
    if len(paths) != 1 or not isinstance(paths[0], str):
        raise AutorizacionDenegada("Ruta de película no única.")
    files = (record.get("intent") or {}).get("files", [])
    if not isinstance(files, list) or sum(
        isinstance(item, dict)
        and isinstance(item.get("destination_relative"), str)
        and "/media/" + item["destination_relative"] == paths[0]
        for item in files
    ) != 1:
        raise AutorizacionDenegada("La publicación no coincide con la película.")
    normalized = {
        "snapshot": snapshot,
        "journals": {
            str(key): [value[0], value[1]]
            for key, value in journals.items()
        },
        "ntfs": sorted(ntfs, key=lambda item: str(item.get("download_id"))),
        "medio_id": medio_id,
        "descarga_id": descarga_id,
    }
    return hashlib.sha256(_canonical(normalized, 200_000)).hexdigest()


def _comprobar_desafio(challenge: dict, now: int) -> None:
    if (
        not isinstance(challenge, dict)
        or set(challenge) != EXPECTED_FIELDS
        or type(challenge["version"]) is not int
        or challenge["version"] != VERSION
        or challenge["accion"] != ACCION
        or not _int_positive(challenge["medio_id"])
        or not _int_positive(challenge["descarga_id"])
        or not isinstance(challenge["prueba_sha256"], str)
        or SHA256.fullmatch(challenge["prueba_sha256"]) is None
        or not isinstance(challenge["nonce"], str)
        or NONCE.fullmatch(challenge["nonce"]) is None
        or not _int_positive(challenge["vence_epoch"])
        or not isinstance(now, int) or isinstance(now, bool)
        or challenge["vence_epoch"] <= now
        or challenge["vence_epoch"] > now + EXPIRE_SECONDS
    ):
        raise AutorizacionDenegada("Desafío inválido, expirado o demasiado largo.")
    _canonical(challenge)


def preparar_desafio(
    resultado: dict,
    *,
    download_id: int,
    prueba_sha256: str,
    now: int,
    nonce: str | None = None,
) -> dict:
    """Requiere preflight SIN otros bloqueos, incluso antes del administrador.

    Un perfil marcando 'vista' NO puede crear un desafío por sí mismo.
    No significa que sea seguro borrar (no hay locks transaccionales).
    """
    if (
        not isinstance(resultado, dict)
        or resultado.get("estado") != "bloqueada"
        or resultado.get("puede_borrarse_ahora") is not False
        or resultado.get("motivos") != [REASON_ADMIN]
        or not _int_positive(resultado.get("medio_id"))
        or not _int_positive(download_id)
        or not isinstance(prueba_sha256, str)
        or SHA256.fullmatch(prueba_sha256) is None
        or not isinstance(now, int) or isinstance(now, bool) or now <= 0
    ):
        raise AutorizacionDenegada("Retirada no reúne garantías previas.")
    challenge = {
        "version": VERSION,
        "accion": ACCION,
        "medio_id": resultado["medio_id"],
        "descarga_id": download_id,
        "prueba_sha256": prueba_sha256,
        "vence_epoch": now + EXPIRE_SECONDS,
        "nonce": nonce if nonce is not None else secrets.token_hex(16),
    }
    _comprobar_desafio(challenge, now)
    return challenge


def preparar_desafio_de_evidencias(
    snapshot: dict,
    journals: dict,
    ntfs: list[dict],
    *,
    medio_id: int,
    descarga_id: int,
    now: int,
) -> dict:
    """Única vía para proponer una aprobación basada en evidencia concreta.

    Un intento con película, descarga o fuente no coincidentes se rechaza.
    """
    from worker.retirement_preflight_0018 import evaluar_retiradas

    fingerprint = huella_evidencias_completas(
        snapshot, journals, ntfs,
        medio_id=medio_id, descarga_id=descarga_id,
    )
    matching = [
        row for row in evaluar_retiradas(snapshot, journals, ntfs)
        if row["medio_id"] == medio_id
    ]
    if len(matching) != 1:
        raise AutorizacionDenegada("La película no está identificada unívocamente.")
    return preparar_desafio(
        matching[0], download_id=descarga_id,
        prueba_sha256=fingerprint, now=now,
    )


def _key_bytes(key: bytes) -> bytes:
    if not isinstance(key, bytes) or len(key) != 32:
        raise AutorizacionDenegada("Clave administrativa no configurada.")
    return key


def firmar_fuera_de_api(
    challenge: dict, key: bytes, confirmacion: str, *, now: int,
) -> dict:
    """Solo para el host de administración; NUNCA exponer por HTTP."""
    _comprobar_desafio(challenge, now)
    _key_bytes(key)
    if confirmacion != (
        f"RETIRAR MEDIO {challenge['medio_id']} DESCARGA {challenge['descarga_id']}"
    ):
        raise AutorizacionDenegada("Confirmación del administrador incorrecta.")
    mac = hmac.digest(key, _canonical(challenge), hashlib.sha256).hex()
    return {"desafio": challenge, "firma": mac}


def verificar_ticket(
    ticket: dict,
    key: bytes,
    *,
    expected_medio: int,
    expected_download: int,
    expected_proof: str,
    now: int,
) -> bool:
    """Firma válida != permiso de borrar. No consume ni modifica archivos."""
    _key_bytes(key)
    if (
        not isinstance(ticket, dict)
        or set(ticket) != {"desafio", "firma"}
        or not isinstance(ticket["firma"], str)
        or SHA256.fullmatch(ticket["firma"]) is None
    ):
        raise AutorizacionDenegada("Aprobación inválida.")
    challenge = ticket["desafio"]
    _comprobar_desafio(challenge, now)
    if (
        challenge["medio_id"] != expected_medio
        or challenge["descarga_id"] != expected_download
        or challenge["prueba_sha256"] != expected_proof
    ):
        raise AutorizacionDenegada("La prueba ha cambiado.")
    signature = hmac.digest(key, _canonical(challenge), hashlib.sha256).hex()
    if not hmac.compare_digest(signature, ticket["firma"]):
        raise AutorizacionDenegada("Firma administrativa incorrecta.")
    return True


def leer_clave_administrador(file: Path) -> bytes:
    """Solo WSL host, nunca desde ruta .env, bind Windows ni proyecto.

    La clave de 32 bytes es generada/provista externamente por el
    administrador. Esta función NO la genera ni imprime.
    """
    path = Path(file)
    try:
        real = path.resolve(strict=True)
        parent = path.parent.resolve(strict=True)
        parent_stat = parent.stat()
        if (
            real != path.absolute()
            or real.parent != parent
            or not stat.S_ISDIR(parent_stat.st_mode)
            or parent_stat.st_uid != os.geteuid()
            or parent_stat.st_mode & 0o077
            or str(real).startswith("/mnt/")
            or "/projects/" in str(real)
        ):
            raise AutorizacionDenegada("Raíz privada administrativa no válida.")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
                or info.st_nlink != 1
                or info.st_size != 32
            ):
                raise AutorizacionDenegada("Clave no tiene propiedad exclusiva.")
            value = os.read(fd, 33)
        finally:
            os.close(fd)
        return _key_bytes(value)
    except OSError as exc:
        raise AutorizacionDenegada("Clave administrativa inaccesible.") from exc


def consumir_ticket_una_vez(
    ticket: dict,
    key: bytes,
    ledger: Path,
    *,
    expected_medio: int,
    expected_download: int,
    expected_proof: str,
    now: int,
) -> dict:
    """Registro de consumo en sandbox privado; NO ACTIVA BORRADO REAL.

    El ejecutor final aún no existe y necesitará bloqueo transaccional de
    qBit/Windows, journal y una nueva revalidación inmediatamente antes
    de cualquier eliminación de originales.
    """
    verificar_ticket(
        ticket, key,
        expected_medio=expected_medio,
        expected_download=expected_download,
        expected_proof=expected_proof, now=now,
    )
    path = Path(ledger)
    directory = path.parent
    folder_stat = directory.stat()
    if (
        not stat.S_ISDIR(folder_stat.st_mode)
        or folder_stat.st_uid != os.geteuid()
        or folder_stat.st_mode & 0o077
        or str(directory.resolve()).startswith("/mnt/")
        or "/projects/" in str(directory.resolve())
    ):
        raise AutorizacionDenegada("Diario de consumo debe ser privado.")
    if path.is_symlink():
        raise AutorizacionDenegada("Diario no puede ser un enlace.")
    if not path.exists():
        # Crear con permisos 0600 ANTES de abrir SQLite: ningún momento
        # intermedio con permisos 0644 bajo el umask predeterminado.
        try:
            created_fd = os.open(
                path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
            )
            os.close(created_fd)
        except FileExistsError:
            pass
        except OSError as exc:
            raise AutorizacionDenegada(
                "No se puede crear el diario administrativo."
            ) from exc
    if path.exists():
        info = path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise AutorizacionDenegada("Diario de consumo no confiable.")
    nonce = ticket["desafio"]["nonce"]
    try:
        with sqlite3.connect(path, timeout=5, isolation_level=None) as db:
            db.execute("PRAGMA busy_timeout=5000")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            db.execute("""
                CREATE TABLE IF NOT EXISTS consumos (
                    nonce TEXT PRIMARY KEY,
                    medio_id INTEGER NOT NULL,
                    descarga_id INTEGER NOT NULL,
                    prueba_sha256 TEXT NOT NULL,
                    consumido_epoch INTEGER NOT NULL
                )
            """)
            # Defensa adicional 0044: el nonce por sí solo NO basta.
            # Otra firma valida con nonce nuevo no puede rearmar un medio
            # o reutilizar una descarga consumida. Si un diario antiguo
            # contiene duplicados, CREATE UNIQUE INDEX falla CERRADO.
            # Los índices se crean en la MISMA transacción que INSERT.
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "consumos_medio_unico_0044 ON consumos(medio_id)"
            )
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "consumos_descarga_unica_0044 ON consumos(descarga_id)"
            )
            # No confiar solo en IF NOT EXISTS: un SQLite preexistente
            # podria tener un indice NO unico o parcial con el mismo
            # nombre. Exigir ambos indices reales, totales y de columna
            # exacta antes de consumir un token administrativo.
            indexes = db.execute("PRAGMA index_list('consumos')").fetchall()
            for name, column in (
                ("consumos_medio_unico_0044", "medio_id"),
                ("consumos_descarga_unica_0044", "descarga_id"),
            ):
                actual = [
                    row for row in indexes
                    if row[1] == name and row[2] == 1 and row[4] == 0
                ]
                members = db.execute(
                    f"PRAGMA index_info('{name}')"
                ).fetchall()
                if (
                    len(actual) != 1 or len(members) != 1
                    or members[0][2] != column
                ):
                    raise AutorizacionDenegada(
                        "Indice de consumo unico no verificable."
                    )
            db.execute(
                "INSERT INTO consumos VALUES (?, ?, ?, ?, ?)",
                (nonce, expected_medio, expected_download, expected_proof, now),
            )
            db.execute("COMMIT")
    except (sqlite3.Error, OSError) as exc:
        raise AutorizacionDenegada(
            "Ticket repetido o diario de consumo no disponible."
        ) from exc
    # La propiedad y permisos 0600 se verifican ANTES del consumo.
    # Nunca habilitar desde aquí operaciones de eliminación.
    return {
        "estado": "consumida_para_ensayo",
        "autoriza_borrado_fisico": False,
    }


def epoch_now() -> int:
    return int(datetime.now(UTC).timestamp())
