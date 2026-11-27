"""Laboratorio 0027 de admisión de reproducción, NO conectado a la API.

Un SQLite privado en una carpeta TEMP GUID permite probar el conflicto entre
nuevas sesiones VIEWTV, peticiones de vídeo en curso y el inicio del drenaje.
El ensayo NO tiene permisos de retiradas, no detiene un stream real ni vigila
clientes que entren directamente a Jellyfin. No es un ejecutor productivo.
"""
from __future__ import annotations

import os
import re
import secrets
import sqlite3
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SANDBOX_NAME = re.compile(r"viewtv-admission-0027-[a-f0-9]{32}\Z")
TOKEN = re.compile(r"[a-f0-9]{48}\Z")
MARKER = "VIEWTV-0027-SOLO-SANDBOX"
STATES = frozenset(("libre", "drenando", "listo_para_preflight"))


class AdmisionRechazada(ValueError):
    """La operación no se puede admitir en las condiciones actuales."""


def _media(media_id: object) -> int:
    if type(media_id) is not int or media_id <= 0 or media_id > 2_147_483_647:
        raise AdmisionRechazada("Medio de prueba no verificable.")
    return media_id


def _token(value: object) -> str:
    if not isinstance(value, str) or TOKEN.fullmatch(value) is None:
        raise AdmisionRechazada("Token de prueba inválido.")
    return value


def _private_dir(root: Path) -> Path:
    if not isinstance(root, Path):
        raise AdmisionRechazada("Sandbox no verificable.")
    try:
        temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
        if root.parent.resolve(strict=True) != temp_root:
            raise AdmisionRechazada("El ensayo está fuera de TEMP.")
        if SANDBOX_NAME.fullmatch(root.name) is None or root.is_symlink():
            raise AdmisionRechazada("Nombre de ensayo no válido.")
        info = root.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise AdmisionRechazada("Carpeta privada no verificable.")
        marker = root / "marca-0027.txt"
        meta = marker.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(meta.st_mode)
            or meta.st_nlink != 1
            or meta.st_uid != os.geteuid()
            or stat.S_IMODE(meta.st_mode) != 0o600
            or marker.read_text(encoding="ascii") != MARKER
        ):
            raise AdmisionRechazada("Marca de prueba inválida.")
        return root
    except (OSError, UnicodeError) as exc:
        raise AdmisionRechazada("Sandbox de ensayo inaccesible.") from exc


class LaboratorioAdmision0027:
    """Admisión compartida entre procesos SOLO de sesiones ficticias.

    BEGIN IMMEDIATE garantiza que las admisiones y el drenaje se ordenen.
    Las solicitudes de un stream no se liberan hasta registrar su fin,
    incluso si su sesión fue cerrada. Crash -> filas atascadas -> bloqueo.
    No expira ni purga automáticamente sesiones o solicitudes.
    """

    def __init__(self, root: Path) -> None:
        self.root = _private_dir(root)
        self.database = self.root / "admisiones.sandbox.db"
        if not self.database.exists():
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(self.database, flags, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        self._check_database()
        with self._transaction() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS peliculas ("
                "id INTEGER PRIMARY KEY, estado TEXT NOT NULL "
                "CHECK (estado IN ('libre','drenando','listo_para_preflight')))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sesiones ("
                "token TEXT PRIMARY KEY, media_id INTEGER NOT NULL,"
                "abierta INTEGER NOT NULL CHECK (abierta IN (0,1)),"
                "FOREIGN KEY(media_id) REFERENCES peliculas(id))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS solicitudes ("
                "token TEXT PRIMARY KEY, sesion TEXT NOT NULL,"
                "FOREIGN KEY(sesion) REFERENCES sesiones(token))"
            )

    def _check_database(self) -> None:
        _private_dir(self.root)
        try:
            info = self.database.stat(follow_symlinks=False)
        except OSError as exc:
            raise AdmisionRechazada("Base de ensayo ausente.") from exc
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise AdmisionRechazada("Base de ensayo no privada.")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self._check_database()
        conn = sqlite3.connect(str(self.database), timeout=2)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.rollback()
                raise
            else:
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _state(conn: sqlite3.Connection, medio_id: int) -> str:
        conn.execute(
            "INSERT OR IGNORE INTO peliculas(id, estado) VALUES (?, 'libre')",
            (medio_id,),
        )
        result = conn.execute(
            "SELECT estado FROM peliculas WHERE id=?", (medio_id,)
        ).fetchone()
        if result is None or result[0] not in STATES:
            raise AdmisionRechazada("Estado de laboratorio no confiable.")
        return result[0]

    @staticmethod
    def _update_finished(conn: sqlite3.Connection, medio_id: int) -> None:
        state = LaboratorioAdmision0027._state(conn, medio_id)
        left = conn.execute(
            "SELECT COUNT(*) FROM sesiones WHERE media_id=?", (medio_id,)
        ).fetchone()[0]
        if state == "drenando" and left == 0:
            conn.execute(
                "UPDATE peliculas SET estado='listo_para_preflight' WHERE id=?",
                (medio_id,),
            )

    def abrir_sesion(self, medio_id: int) -> str:
        media = _media(medio_id)
        ticket = secrets.token_hex(24)
        with self._transaction() as conn:
            if self._state(conn, media) != "libre":
                raise AdmisionRechazada("Admisión cerrada para este medio.")
            conn.execute(
                "INSERT INTO sesiones(token,media_id,abierta) VALUES(?,?,1)",
                (ticket, media),
            )
        return ticket

    def iniciar_peticion(self, medio_id: int, sesion: str) -> str:
        media, token = _media(medio_id), _token(sesion)
        io = secrets.token_hex(24)
        with self._transaction() as conn:
            state = self._state(conn, media)
            if state not in ("libre", "drenando"):
                raise AdmisionRechazada("Petición de vídeo no admitida.")
            row = conn.execute(
                "SELECT abierta FROM sesiones WHERE token=? AND media_id=?",
                (token, media),
            ).fetchone()
            if row is None or row[0] != 1:
                raise AdmisionRechazada("Sesión cerrada, ajena o inválida.")
            conn.execute(
                "INSERT INTO solicitudes(token,sesion) VALUES(?,?)", (io, token)
            )
        return io

    def terminar_peticion(self, medio_id: int, sesion: str, io: str) -> None:
        media, session_token, io_token = _media(medio_id), _token(sesion), _token(io)
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT s.abierta FROM solicitudes AS r "
                "JOIN sesiones AS s ON s.token=r.sesion "
                "WHERE r.token=? AND s.token=? AND s.media_id=?",
                (io_token, session_token, media),
            ).fetchone()
            if row is None:
                raise AdmisionRechazada("Petición ajena o ya terminada.")
            conn.execute("DELETE FROM solicitudes WHERE token=?", (io_token,))
            if row[0] == 0:
                conn.execute(
                    "DELETE FROM sesiones WHERE token=? AND "
                    "NOT EXISTS(SELECT 1 FROM solicitudes WHERE sesion=?)",
                    (session_token, session_token),
                )
            self._update_finished(conn, media)

    def cerrar_sesion(self, medio_id: int, sesion: str) -> None:
        media, token = _media(medio_id), _token(sesion)
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT abierta FROM sesiones WHERE token=? AND media_id=?",
                (token, media),
            ).fetchone()
            if row is None or row[0] != 1:
                raise AdmisionRechazada("Sesión ajena o ya cerrada.")
            conn.execute(
                "UPDATE sesiones SET abierta=0 WHERE token=?", (token,)
            )
            conn.execute(
                "DELETE FROM sesiones WHERE token=? AND "
                "NOT EXISTS(SELECT 1 FROM solicitudes WHERE sesion=?)",
                (token, token),
            )
            self._update_finished(conn, media)

    def iniciar_drenaje(self, medio_id: int) -> dict:
        media = _media(medio_id)
        with self._transaction() as conn:
            state = self._state(conn, media)
            if state == "libre":
                conn.execute(
                    "UPDATE peliculas SET estado='drenando' WHERE id=?",
                    (media,),
                )
            self._update_finished(conn, media)
            status = self._state(conn, media)
        return {
            "estado": status,
            "no_hay_sesiones_viewtv": status == "listo_para_preflight",
            "jellyfin_externo_controlado": False,
            "qbit_controlado": False,
            "autoriza_borrado_fisico": False,
        }

    def observar(self, medio_id: int) -> dict:
        media = _media(medio_id)
        with self._transaction() as conn:
            state = self._state(conn, media)
            sessions = conn.execute(
                "SELECT COUNT(*) FROM sesiones WHERE media_id=?",
                (media,),
            ).fetchone()[0]
            requests = conn.execute(
                "SELECT COUNT(*) FROM solicitudes WHERE sesion IN "
                "(SELECT token FROM sesiones WHERE media_id=?)",
                (media,),
            ).fetchone()[0]
        return {
            "estado": state,
            "sesiones_viewtv_pendientes": sessions,
            "peticiones_video_pendientes": requests,
            "se_prohibe_nueva_sesion": state != "libre",
            "no_hay_sesiones_viewtv": state == "listo_para_preflight",
            "autoriza_borrado_fisico": False,
        }
