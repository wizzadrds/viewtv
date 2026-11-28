"""0044: reserva de retiro por película, descarga y File ID, SOLO LAB.

Comparte SQLite TEMP privada con la custodia ficticia 0038 y el cercado
START 0039. Consume una firma administrativa de prueba en una sola
transacción, con unicidad por medio, descarga, hash, nonce y File ID.

Ni la firma ni esta reserva representan aislamiento kernel, Jellyfin/HLS
cerrado, qBit productivo protegido, confirmación de bytes liberados ni
permiso de borrado. NO posee métodos de eliminación ni rutas de producción.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from typing import Any

import httpx

from worker.retirement_authorization_0019 import (
    AutorizacionDenegada,
    huella_evidencias_completas,
    verificar_ticket,
)
from worker.retirement_qbit_stop_lab_0038 import (
    CustodiaQbitLab0038,
    ParadaLabRechazada,
    _canonical,
)

HEX = re.compile(r"[a-f0-9]{64}\Z")
HASH = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")
MAX_ID = 2**31 - 1
FIELDS = frozenset({
    "original", "publicado",
})
IDENTITY = frozenset({
    "volume", "file_index_high", "file_index_low",
    "hardlinks", "size_bytes", "sha256",
})


class ReservaRechazada(ValueError):
    """La autorización nunca se transforma en permiso de borrado."""


def _id(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_ID:
        raise ReservaRechazada("Identidad de película/descarga inválida.")
    return value


def _files_ntfs(exact_files: object) -> dict[str, Any]:
    """Dos nombres del mismo File ID y exactamente dos referencias.

    Estos son datos del ensayo, NO un acceso a un archivo Windows real.
    """
    if not isinstance(exact_files, Mapping) or set(exact_files) != FIELDS:
        raise ReservaRechazada("Faltan dos identidades NTFS.")
    validated = {}
    for name in ("original", "publicado"):
        record = exact_files[name]
        if not isinstance(record, dict) or set(record) != IDENTITY:
            raise ReservaRechazada("Prueba NTFS incompleta.")
        for field in ("volume", "file_index_high", "file_index_low"):
            if (
                type(record[field]) is not int or record[field] < 0
                or record[field] >= 2**32
            ):
                raise ReservaRechazada("File ID inválido.")
        if (
            type(record["hardlinks"]) is not int
            or record["hardlinks"] != 2
            or type(record["size_bytes"]) is not int
            or not 0 < record["size_bytes"] <= 2**40
            or not isinstance(record["sha256"], str)
            or HEX.fullmatch(record["sha256"]) is None
        ):
            raise ReservaRechazada("NTFS no demuestra exactamente dos enlaces.")
        validated[name] = dict(record)
    if validated["original"] != validated["publicado"]:
        raise ReservaRechazada("Los dos nombres no tienen la misma identidad.")
    return validated["original"]


def prueba_reserva_0044(
    snapshot: dict,
    journals: dict,
    ntfs: list[dict],
    *,
    medio_id: int,
    descarga_id: int,
    file_ids: object,
) -> str:
    """Huella de preflight + dos nombres de un mismo File ID ficticio."""
    medio, descarga = _id(medio_id), _id(descarga_id)
    data = _files_ntfs(file_ids)
    try:
        original = huella_evidencias_completas(
            snapshot, journals, ntfs, medio_id=medio, descarga_id=descarga,
        )
        record = snapshot["qbittorrent"][str(descarga)]
        _, torrent_hash = _canonical(record["torrent"], record["files"])
        publication = journals[descarga][0]["intent"]
        video_files = [
            f for f in publication["files"]
            if f.get("destination_relative", "").lower().endswith(
                (".mkv", ".mp4", ".avi", ".m4v")
            )
        ]
        if (
            torrent_hash != publication["torrent_hash"]
            or len(video_files) != 1
            or video_files[0]["size_bytes"] != data["size_bytes"]
        ):
            raise ReservaRechazada("File ID no vinculado al archivo publicado.")
    except (KeyError, IndexError, TypeError, ValueError, AutorizacionDenegada) as exc:
        raise ReservaRechazada("No hay prueba completa de una película.") from exc
    binding = {
        "scope": "VIEWTV_0044_SOLO_SANDBOX",
        "medio_id": medio, "descarga_id": descarga,
        "preflight_sha256": original,
        "torrent_hash": torrent_hash,
        "file_id": data,
    }
    encoded = json.dumps(
        binding, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


class ReservaFilmFicticia0044:
    """Unica reserva durable bajo el mismo BEGIN IMMEDIATE de qBit 0038."""

    def __init__(self, custodia: CustodiaQbitLab0038) -> None:
        if not isinstance(custodia, CustodiaQbitLab0038):
            raise ReservaRechazada("No existe custodia sintética.")
        self.custodia = custodia
        # Cualquier instancia de transporte real se rechaza en _tx+init 0038.
        with self.custodia._tx() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reservas_film_0044 ("
                "medio INTEGER NOT NULL UNIQUE,"
                "descarga INTEGER NOT NULL UNIQUE,"
                "torrent_hash TEXT NOT NULL UNIQUE,"
                "nonce TEXT NOT NULL UNIQUE,"
                "proof TEXT NOT NULL,"
                "file_id TEXT NOT NULL UNIQUE,"
                "estado TEXT NOT NULL CHECK("
                "estado='reservada_no_ejecutable'),"
                "PRIMARY KEY(medio,descarga))"
            )

    def reservar(
        self,
        ticket: dict,
        key: bytes,
        *,
        snapshot_inicial: dict,
        snapshot_final: dict,
        journals: dict,
        ntfs: list[dict],
        file_ids: object,
        medio_id: int,
        descarga_id: int,
        now: int,
    ) -> dict[str, object]:
        medio, descarga = _id(medio_id), _id(descarga_id)
        exact = _files_ntfs(file_ids)
        first = prueba_reserva_0044(
            snapshot_inicial, journals, ntfs,
            medio_id=medio, descarga_id=descarga, file_ids=file_ids,
        )
        last = prueba_reserva_0044(
            snapshot_final, journals, ntfs,
            medio_id=medio, descarga_id=descarga, file_ids=file_ids,
        )
        if first != last:
            raise ReservaRechazada("Las evidencias cambiaron antes de reservar.")
        try:
            verificar_ticket(
                ticket, key,
                expected_medio=medio, expected_download=descarga,
                expected_proof=last, now=now,
            )
            source = snapshot_final["qbittorrent"][str(descarga)]
            fingerprint, torrent_hash = _canonical(
                source["torrent"], source["files"],
            )
            _, record_hash = _canonical(
                snapshot_inicial["qbittorrent"][str(descarga)]["torrent"],
                snapshot_inicial["qbittorrent"][str(descarga)]["files"],
            )
            if torrent_hash != record_hash or HASH.fullmatch(torrent_hash) is None:
                raise ReservaRechazada("Torrent cambió durante el ensayo.")
            digest = hashlib.sha256(fingerprint).hexdigest()
            nonce = ticket["desafio"]["nonce"]
            if not isinstance(nonce, str) or not re.fullmatch(
                r"[a-f0-9]{32}", nonce,
            ):
                raise ReservaRechazada("Identificador de aprobación no válido.")
        except (KeyError, ValueError, TypeError, AutorizacionDenegada) as exc:
            raise ReservaRechazada("Firma o torrent de ensayo no verificable.") from exc
        # Evitar que el diario qBit parado o un cliente WebUI distinto
        # suplante dos lecturas nuevas del torrent. SOLO MockTransport.
        if not isinstance(
            getattr(self.custodia.qbit, "_transport", None),
            httpx.MockTransport,
        ):
            raise ReservaRechazada("No se permite transporte real.")
        try:
            observed = [
                self.custodia._read_qbit(torrent_hash, digest)
                for _ in range(2)
            ]
        except (ParadaLabRechazada, ValueError, TypeError, OSError) as exc:
            raise ReservaRechazada("Observación qBit no verificable.") from exc
        if any(state not in {"stoppedUP", "pausedUP"} for state in observed):
            raise ReservaRechazada("Torrent de prueba fue reanudado.")
        file_id = ":".join(str(exact[field]) for field in (
            "volume", "file_index_high", "file_index_low",
        ))
        try:
            # La misma BEGIN IMMEDIATE ordena reservar con el START del 0039,
            # el stop del 0038 y la tabla de consumo film-único.
            with self.custodia._tx() as conn:
                row = conn.execute(
                    "SELECT medio,hash,huella,estado FROM custodia "
                    "WHERE descarga=?",
                    (descarga,),
                ).fetchone()
                if (
                    row is None or len(row) != 4 or
                    row != (medio, torrent_hash, digest, "parada_observada")
                ):
                    raise ReservaRechazada(
                        "qBit no está custodiado para exactamente este medio."
                    )
                conn.execute(
                    "INSERT INTO reservas_film_0044"
                    "(medio,descarga,torrent_hash,nonce,proof,file_id,estado)"
                    " VALUES(?,?,?,?,?,?,'reservada_no_ejecutable')",
                    (medio, descarga, torrent_hash, nonce, last, file_id),
                )
        except (sqlite3.Error, OSError, ParadaLabRechazada) as exc:
            raise ReservaRechazada(
                "Reserva ya consumida o diario privado no disponible."
            ) from exc
        return {
            "estado": "reservada_no_ejecutable",
            "medio_id": medio,
            "descarga_id": descarga,
            "ticket_consumido_para_ensayo": True,
            "custodia_productiva_demostrada": False,
            "puede_iniciar_unlink": False,
            "autoriza_borrado_fisico": False,
            "torrents_reales_modificados": 0,
            "peliculas_reales_borradas": 0,
        }

    def estado(self, medio_id: int) -> dict:
        medio = _id(medio_id)
        with self.custodia._tx() as conn:
            rows = conn.execute(
                "SELECT estado FROM reservas_film_0044 WHERE medio=?",
                (medio,),
            ).fetchall()
        if len(rows) != 1 or rows[0][0] != "reservada_no_ejecutable":
            raise ReservaRechazada("Reserva no verificable.")
        return {
            "estado": "reservada_no_ejecutable",
            "autoriza_borrado_fisico": False,
            "puede_iniciar_unlink": False,
        }
