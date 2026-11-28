"""0038: custodia durable qBit por descarga, SOLO en sandbox y MockTransport.

Nunca conecta a qBittorrent real. Un POST stop solo se envía al mock tras
registrar la intención durable (evita repetirlo tras una caída). El estado
observado NO equivale a una barrera contra reinicios/GUI/otros WebUI ni
autoriza borrar hardlinks, torrents, extras o películas de producción.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx

from worker.retirement_playback_admission_0027 import _private_dir
from worker.retirement_preflight_0018 import HASH_RE, TORRENT_ROOT, _valid_relative
from worker.retirement_qbit_custody_0026 import (
    CustodiaNoConfiable,
    _manifest,
    evaluar_custodia_qbit,
)
from worker.retirement_qbit_start_intent_lab_0046 import (
    InicioAmbiguo0046,
    comprobar_inicio_0046,
    hubo_inicio_0046,
    inicializar_inicio_0046,
)

STATES = frozenset({
    "registrada", "orden_pendiente", "orden_enviada",
    "parada_observada", "bloqueada",
})
SHA_RE = re.compile(r"[a-f0-9]{64}\Z")


class ParadaLabRechazada(ValueError):
    """Denegación sin exponer hash ni metadatos del usuario."""


def _id(value: object) -> int:
    if type(value) is not int or not 0 < value <= 2_147_483_647:
        raise ParadaLabRechazada("Identidad no verificable.")
    return value


def _canonical(torrent: dict, files: list) -> tuple[bytes, str]:
    if (
        not isinstance(torrent, dict) or not isinstance(files, list)
        or not 1 <= len(files) <= 100
    ):
        raise ParadaLabRechazada("qBit sin evidencia de archivos.")
    hash_ = torrent.get("hash")
    if (
        not isinstance(hash_, str) or HASH_RE.fullmatch(hash_) is None
        or not isinstance(torrent.get("tags"), str)
        or not isinstance(torrent.get("save_path"), str)
        or str(Path(torrent["save_path"]).name) == ""
        or str(torrent["save_path"]).casefold() != str(TORRENT_ROOT).casefold()
        or type(torrent.get("progress")) not in (int, float)
        or torrent["progress"] != 1
    ):
        raise ParadaLabRechazada("Torrent no verificable.")
    sorted_files: list[tuple] = []
    seen: set[str] = set()
    for record in files:
        if not isinstance(record, dict):
            raise ParadaLabRechazada("Archivo qBit no verificable.")
        name = record.get("name")
        if not isinstance(name, str):
            raise ParadaLabRechazada("Archivo qBit no verificable.")
        parts = _valid_relative(name.replace("\\", "/"))
        if not parts:
            raise ParadaLabRechazada("Nombre qBit no canónico.")
        key = "/".join(parts).casefold()
        if key in seen:
            raise ParadaLabRechazada("Archivo qBit repetido.")
        seen.add(key)
        if (
            type(record.get("size")) is not int or record["size"] <= 0
            or type(record.get("progress")) not in (int, float)
            or record["progress"] != 1
            or type(record.get("priority")) is not int
            or record["priority"] < 0
        ):
            raise ParadaLabRechazada("Archivo qBit no completo.")
        sorted_files.append((
            key, record["size"], record["progress"], record["priority"],
        ))
    canon = {
        "hash": hash_.casefold(), "tags": torrent["tags"],
        "save_path": torrent["save_path"].casefold(),
        "progress": torrent["progress"],
        "files": sorted(sorted_files),
    }
    data = json.dumps(
        canon, sort_keys=True, ensure_ascii=True, allow_nan=False,
        separators=(",", ":"),
    ).encode("ascii")
    return data, hash_.casefold()


class CustodiaQbitLab0038:
    """Autoridad SQLite TEMP, con único POST stop a transporte HTTP simulado."""

    def __init__(self, root: Path, qbittorrent: object) -> None:
        _private_dir(root)
        # Excluir explícitamente transportes reales, incluso si se suministra
        # una URL legítima, para que NUNCA se pare un torrent de producción.
        if not isinstance(getattr(qbittorrent, "_transport", None), httpx.MockTransport):
            raise ParadaLabRechazada("Se exige qBittorrent simulado.")
        self.root = root
        self.qbit = qbittorrent
        self.db = root / "qbit-custodia-0038.sandbox.db"
        nueva_base = False
        if not self.db.exists():
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(self.db, flags, 0o600)
                os.close(fd)
                nueva_base = True
            except FileExistsError:
                pass
        with self._tx() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS custodia ("
                "descarga INTEGER PRIMARY KEY,"
                "medio INTEGER NOT NULL,"
                "hash TEXT NOT NULL UNIQUE,"
                "huella TEXT NOT NULL,"
                "estado TEXT NOT NULL CHECK(estado IN "
                "('registrada','orden_pendiente','orden_enviada',"
                "'parada_observada','bloqueada')))"
            )
            # No crear una tabla de START desaparecida en una base vieja:
            # hacerlo borraría la prueba de un START iniciado antes del crash.
            if nueva_base:
                inicializar_inicio_0046(con)
            else:
                comprobar_inicio_0046(con)

    def _check(self) -> None:
        _private_dir(self.root)
        info = self.db.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ParadaLabRechazada("Diario de custodia sin privacidad.")

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        self._check()
        con = sqlite3.connect(str(self.db), timeout=3)
        try:
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("PRAGMA synchronous=FULL")
            con.execute("PRAGMA journal_mode=DELETE")
            con.execute("BEGIN IMMEDIATE")
            try:
                yield con
            except BaseException:
                con.rollback()
                raise
            else:
                con.commit()
        finally:
            con.close()

    @staticmethod
    def _row(con: sqlite3.Connection, descarga: int) -> tuple:
        row = con.execute(
            "SELECT medio,hash,huella,estado FROM custodia WHERE descarga=?",
            (descarga,),
        ).fetchone()
        if row is None or row[3] not in STATES or SHA_RE.fullmatch(row[2]) is None:
            raise ParadaLabRechazada("Custodia ausente o inválida.")
        return row

    def registrar(self, medio_id: int, descarga_id: int,
                 snapshot: dict, journals: dict) -> None:
        medio, descarga = _id(medio_id), _id(descarga_id)
        try:
            summary = evaluar_custodia_qbit(snapshot, journals)
            records = [d for d in snapshot["descargas"] if d.get("id") == descarga]
            movies = [m for m in snapshot["peliculas"] if m.get("medio_id") == medio]
            if len(records) != 1 or len(movies) != 1:
                raise ParadaLabRechazada("Medio y descarga no encontrados.")
            record = records[0]
            # Solo un diario, medio exacto vinculado por TMDB de solicitud;
            # este vínculo no sustituye el certificado total 0018.
            if (
                record.get("estado") != "completada"
                or record.get("estado_verificacion") != "verificada"
                or record.get("verificada") is not True
                or record.get("solicitud", {}).get("tmdb_id") != movies[0].get("tmdb_id")
            ):
                raise ParadaLabRechazada("Descarga sin identidad verificada.")
            expected_files = _manifest(journals[descarga], descarga)
            qbit_record = snapshot["qbittorrent"][str(descarga)]
            torrent = qbit_record["torrent"]
            files = qbit_record["files"]
            content, hash_ = _canonical(torrent, files)
            if hash_ != record.get("hash") or hash_ != (
                journals[descarga][0]["intent"]["torrent_hash"]
            ):
                raise ParadaLabRechazada("Hash fuera del diario.")
            if (
                "viewtv-descarga-" + str(descarga) not in
                torrent["tags"].split(",")
                or summary["torrent_propiedad_o_ruta_inconsistente"] != 0
                or summary["archivos_con_tamano_incompatible"] != 0
                or summary["archivos_con_progreso_incompleto"] != 0
            ):
                raise ParadaLabRechazada("Torrent sin propiedad única.")
            observed_sizes = {
                file_info[0]: file_info[1]
                for file_info in json.loads(content)["files"]
            }
            if any(
                observed_sizes.get(name) != size
                for name, size in expected_files.items()
            ):
                raise ParadaLabRechazada("Archivos publicados no presentes.")
            huella = hashlib.sha256(content).hexdigest()
        except (KeyError, IndexError, TypeError, CustodiaNoConfiable) as exc:
            raise ParadaLabRechazada("Evidencia de origen incompleta.") from exc

        with self._tx() as con:
            try:
                if hubo_inicio_0046(con, hash_):
                    raise ParadaLabRechazada(
                        "START anterior: exige reconciliación antes de retirar."
                    )
            except InicioAmbiguo0046 as exc:
                raise ParadaLabRechazada(
                    "Bitácora START de laboratorio no verificable."
                ) from exc
            if con.execute("SELECT 1 FROM custodia").fetchone() is not None:
                raise ParadaLabRechazada("El laboratorio ya tiene una custodia.")
            con.execute(
                "INSERT INTO custodia(descarga,medio,hash,huella,estado)"
                " VALUES(?,?,?,?,'registrada')",
                (descarga, medio, hash_, huella),
            )

    def _read_qbit(self, hash_: str, huella: str) -> str:
        # Nada de hashes=all; no aceptar extras ni reordenamientos que
        # no pertenezcan al mismo torrent.
        records = self.qbit.torrents_info([hash_])
        if not isinstance(records, list) or len(records) != 1:
            raise ParadaLabRechazada("Torrent exacto no recuperado.")
        torrent = records[0]
        if not isinstance(torrent, dict) or torrent.get("hash") != hash_:
            raise ParadaLabRechazada("Hash de respuesta inesperado.")
        state = torrent.get("state")
        if not isinstance(state, str) or not state:
            raise ParadaLabRechazada("Estado qBit no válido.")
        files = self.qbit.torrent_files(hash_)
        data, _ = _canonical(torrent, files)
        if hashlib.sha256(data).hexdigest() != huella:
            raise ParadaLabRechazada("qBit cambió archivos o procedencia.")
        return state

    def ordenar_stop(self, descarga_id: int) -> None:
        descarga = _id(descarga_id)
        with self._tx() as con:
            _, hash_, huella, state = self._row(con, descarga)
            if state != "registrada":
                raise ParadaLabRechazada("Parada duplicada o estado incierto.")
        previous = self._read_qbit(hash_, huella)
        if previous not in {
            "uploading", "stalledUP", "queuedUP", "forcedUP",
            "pausedUP", "stoppedUP",
        }:
            raise ParadaLabRechazada("Torrent sin estado seguro para laboratorio.")
        # Persistir ANTES del POST: si se pierde la respuesta o cae el
        # proceso, nunca se reenvía la orden sin conciliación explícita.
        with self._tx() as con:
            _, hash2, _, state = self._row(con, descarga)
            if state != "registrada" or hash2 != hash_:
                raise ParadaLabRechazada("La custodia cambió durante el preflight.")
            con.execute(
                "UPDATE custodia SET estado='orden_pendiente' WHERE descarga=?",
                (descarga,),
            )
        # MockTransport obligatorio desde constructor.
        if previous not in {"pausedUP", "stoppedUP"}:
            self.qbit.stop_torrent(hash_)
        with self._tx() as con:
            _, _, _, current = self._row(con, descarga)
            if current != "orden_pendiente":
                raise ParadaLabRechazada("Orden pendiente modificada.")
            con.execute(
                "UPDATE custodia SET estado='orden_enviada' WHERE descarga=?",
                (descarga,),
            )

    def observar(self, descarga_id: int) -> dict:
        descarga = _id(descarga_id)
        with self._tx() as con:
            _, hash_, huella, state = self._row(con, descarga)
            if state not in {
                "orden_pendiente", "orden_enviada", "parada_observada",
            }:
                raise ParadaLabRechazada("La custodia no admite revisión.")
        stable = False
        try:
            stable = all(
                self._read_qbit(hash_, huella) in {"pausedUP", "stoppedUP"}
                for _ in range(2)
            )
        except (ValueError, RuntimeError, OSError):
            stable = False
        with self._tx() as con:
            _, _, _, current = self._row(con, descarga)
            if current != state:
                raise ParadaLabRechazada("La custodia cambió entre lecturas.")
            new = "parada_observada" if stable else "bloqueada"
            con.execute(
                "UPDATE custodia SET estado=? WHERE descarga=?",
                (new, descarga),
            )
        return {
            "estado": new,
            "parada_observada": stable,
            "custodia_qbit_transaccional_real": False,
            "autoriza_borrado_fisico": False,
            "torrents_productivos_modificados": 0,
            "peliculas_borradas": 0,
        }

    def estado(self, descarga_id: int) -> dict:
        descarga = _id(descarga_id)
        with self._tx() as con:
            _, _, _, state = self._row(con, descarga)
        return {
            "estado": state,
            "custodia_qbit_transaccional_real": False,
            "autoriza_borrado_fisico": False,
        }
