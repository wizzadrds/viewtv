"""0046: bitácora durable de START qBit para custodia, solo laboratorio.

La intención se confirma ANTES de emitir el POST mock. No existe ningún
método para borrar una entrada, liberar una custodia ni autorizar unlink.
"""
from __future__ import annotations

import re
import sqlite3

START_SCHEMA_0046 = (
    "CREATE TABLE IF NOT EXISTS inicios_qbit_0046 ("
    "hash TEXT PRIMARY KEY COLLATE NOCASE,"
    "estado TEXT NOT NULL CHECK(estado IN "
    "('pendiente','confirmada','respuesta_incierta')))"
)
_HASH = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")
_STATES = frozenset({"pendiente", "confirmada", "respuesta_incierta"})


class InicioAmbiguo0046(ValueError):
    """No debe aceptarse custodia de un START con resultado ambiguo."""


def comprobar_inicio_0046(db: sqlite3.Connection) -> None:
    """Validar DDL, integridad y entradas existentes, sin crear nada."""
    row = db.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type='table' AND name='inicios_qbit_0046'"
    ).fetchone()
    if row is None or row[0] not in (
        START_SCHEMA_0046,
        START_SCHEMA_0046.replace(" IF NOT EXISTS", ""),
    ):
        raise InicioAmbiguo0046("Bitácora de START ausente o alterada.")
    records = db.execute(
        "SELECT hash,estado FROM inicios_qbit_0046"
    ).fetchall()
    for hash_, state in records:
        if (
            not isinstance(hash_, str)
            or _HASH.fullmatch(hash_) is None
            or state not in _STATES
        ):
            raise InicioAmbiguo0046("Entrada START no verificable.")


def inicializar_inicio_0046(db: sqlite3.Connection) -> None:
    db.execute(START_SCHEMA_0046)
    comprobar_inicio_0046(db)


def hubo_inicio_0046(db: sqlite3.Connection, hash_: str) -> bool:
    comprobar_inicio_0046(db)
    if not isinstance(hash_, str) or _HASH.fullmatch(hash_.casefold()) is None:
        raise InicioAmbiguo0046("Hash no verificable.")
    return db.execute(
        "SELECT 1 FROM inicios_qbit_0046 WHERE hash=?",
        (hash_.casefold(),),
    ).fetchone() is not None


def estado_inicio_0046(db: sqlite3.Connection, hash_: str) -> dict:
    comprobar_inicio_0046(db)
    if not isinstance(hash_, str) or _HASH.fullmatch(hash_.casefold()) is None:
        raise InicioAmbiguo0046("Hash no verificable.")
    row = db.execute(
        "SELECT estado FROM inicios_qbit_0046 WHERE hash=?",
        (hash_.casefold(),),
    ).fetchone()
    if row is None:
        raise InicioAmbiguo0046("No existe constancia de START.")
    return {
        "estado": row[0],
        "puede_registrar_retirada": False,
        "puede_borrar_archivos": False,
        "es_aislamiento_qbit_productivo": False,
    }
