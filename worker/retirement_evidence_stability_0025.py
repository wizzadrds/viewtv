"""0025 — coherencia entre dos fotografías completas; NO reserva archivos.

Compara DOS consultas independientes a SQLite/Jellyfin/qBittorrent, DOS
lecturas integrales de diarios y DOS auditorías Windows/NTFS. Cualquier
discrepancia bloquea la revisión. Nunca autoriza retirar medios: dos
fotografías iguales NO garantizan que qBit o Jellyfin no cambien después.
No muestra títulos, hashes, rutas, nombres ni identidad de perfiles.
"""
from __future__ import annotations

import json
import re
from typing import Any

MAX_SNAPSHOT_BYTES = 2_000_000
MAX_JOURNALS = 500
MAX_NTFS = 500
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


class EvidenciaInestable(ValueError):
    """Denegación sin detalles privados."""


def _json_bytes(value: Any, *, limit: int) -> bytes:
    try:
        encoded = json.dumps(
            value, ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise EvidenciaInestable("Evidencia no serializable.") from exc
    if not 2 <= len(encoded) <= limit:
        raise EvidenciaInestable("Evidencia fuera de límites.")
    return encoded


def _snapshot(snapshot: Any) -> bytes:
    if (
        not isinstance(snapshot, dict)
        or not isinstance(snapshot.get("peliculas"), list)
        or not isinstance(snapshot.get("perfiles_activos"), list)
        or not isinstance(snapshot.get("descargas"), list)
        or not isinstance(snapshot.get("jellyfin"), dict)
        or snapshot["jellyfin"].get("estado") != "ok"
        or not isinstance(snapshot["jellyfin"].get("elementos"), list)
        or not isinstance(snapshot.get("qbittorrent"), dict)
        or len(snapshot["peliculas"]) > 1000
        or len(snapshot["descargas"]) > 1000
        or len(snapshot["jellyfin"]["elementos"]) > 10000
        or len(snapshot["qbittorrent"]) > 1000
    ):
        raise EvidenciaInestable("Fotografía completa no verificable.")
    return _json_bytes(snapshot, limit=MAX_SNAPSHOT_BYTES)


def _journals(journals: Any) -> bytes:
    if not isinstance(journals, dict) or len(journals) > MAX_JOURNALS:
        raise EvidenciaInestable("Diarios no verificables.")
    records: list[tuple[int, dict, str]] = []
    for id_, pair in journals.items():
        if type(id_) is not int or id_ <= 0:
            raise EvidenciaInestable("Identificador de diario inválido.")
        if (
            not isinstance(pair, tuple) or len(pair) != 2
            or not isinstance(pair[0], dict)
            or pair[0].get("download_id") != id_
            or not isinstance(pair[1], str)
            or SHA256.fullmatch(pair[1]) is None
        ):
            raise EvidenciaInestable("Diario inconsistente.")
        records.append((id_, pair[0], pair[1]))
    return _json_bytes(
        sorted(records, key=lambda record: record[0]),
        limit=MAX_SNAPSHOT_BYTES,
    )


def _ntfs(rows: Any) -> bytes:
    if not isinstance(rows, list) or len(rows) > MAX_NTFS:
        raise EvidenciaInestable("Pruebas Windows no verificables.")
    ids: set[int] = set()
    for item in rows:
        if not isinstance(item, dict):
            raise EvidenciaInestable("Fila NTFS irregular.")
        id_ = item.get("download_id")
        sha = item.get("journal_sha256")
        if (
            type(id_) is not int or id_ <= 0 or id_ in ids
            or type(item.get("ntfs_verified")) is not bool
            or not isinstance(sha, str)
            or SHA256.fullmatch(sha) is None
            or type(item.get("archivos")) is not int
            or not 1 <= item["archivos"] <= 100
        ):
            raise EvidenciaInestable("NTFS no tiene identidad única.")
        ids.add(id_)
    return _json_bytes(
        sorted(rows, key=lambda row: row["download_id"]),
        limit=MAX_SNAPSHOT_BYTES,
    )


def certificar_doble_lectura(
    primer_snapshot: dict,
    ultimo_snapshot: dict,
    primeros_diarios: dict,
    ultimos_diarios: dict,
    primer_ntfs: list,
    ultimo_ntfs: list,
) -> dict:
    """Coherencia observada solamente, nunca exclusión o bloqueo duradero.

    Los cambios incluso de otra película se consideran inestables para
    evitar usar evidencia de distinta época en un futuro proceso crítico.
    """
    pairs = (
        (_snapshot(primer_snapshot), _snapshot(ultimo_snapshot)),
        (_journals(primeros_diarios), _journals(ultimos_diarios)),
        (_ntfs(primer_ntfs), _ntfs(ultimo_ntfs)),
    )
    if any(first != last for first, last in pairs):
        raise EvidenciaInestable("Las fuentes cambiaron entre consultas.")
    return {
        "estado": "dos_lecturas_coincidentes",
        "snapshots_completos": 2,
        "lecturas_diarios": 2,
        "auditorias_ntfs": 2,
        "inmovilizacion_qbit_y_jellyfin": False,
        "habilita_borrado_fisico": False,
    }
