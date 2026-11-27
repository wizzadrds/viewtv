"""0031: autoridad HLS v2 durable, exclusivamente en sandbox TEMP privado.

Extiende 0029: perfil + JWT + sesión persistente + generación por película,
con reserva de cada GET en la MISMA transacción que consulta drenaje.
Una caída deja sesiones/lecturas bloqueantes. No ejecuta borrados ni
controla las vías directas de Jellyfin, qBittorrent o NTFS.
"""
from __future__ import annotations

import re
import secrets
import sqlite3

from worker.retirement_playback_admission_0027 import (
    AdmisionRechazada,
    _media,
    _token,
)
from worker.retirement_profile_admission_0029 import (
    AdmisionPerfilLab0029,
    _profile,
)

ROOT_RE = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
FINGERPRINT_RE = re.compile(r"[a-f0-9]{64}\Z")


def _identity(root: object, fingerprint: object) -> tuple[str, str]:
    if (
        not isinstance(root, str) or ROOT_RE.fullmatch(root) is None
        or not isinstance(fingerprint, str)
        or FINGERPRINT_RE.fullmatch(fingerprint) is None
    ):
        raise AdmisionRechazada("Contexto HLS no verificable.")
    return root, fingerprint


class AdmisionHLSLab0031(AdmisionPerfilLab0029):
    """Sesiones HLS activas solo en el directorio sandbox exigido por 0027."""

    def __init__(self, root):
        super().__init__(root)
        with self._transaction() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS generaciones_hls ("
                "media_id INTEGER PRIMARY KEY REFERENCES peliculas(id),"
                "generacion INTEGER NOT NULL CHECK "
                "(generacion > 0 AND generacion <= 2147483647))"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sesiones_hls ("
                "sesion TEXT PRIMARY KEY REFERENCES sesiones(token) "
                "ON DELETE CASCADE,"
                "video_root TEXT NOT NULL, "
                "huella_cookie TEXT NOT NULL,"
                "generacion INTEGER NOT NULL CHECK (generacion > 0))"
            )

    @staticmethod
    def _generation(conn: sqlite3.Connection, media_id: int) -> int:
        conn.execute(
            "INSERT OR IGNORE INTO generaciones_hls(media_id,generacion) "
            "VALUES (?,1)", (media_id,),
        )
        row = conn.execute(
            "SELECT generacion FROM generaciones_hls WHERE media_id=?", (media_id,),
        ).fetchone()
        if (
            row is None or type(row[0]) is not int
            or not 0 < row[0] <= 2_147_483_647
        ):
            raise AdmisionRechazada("Generación HLS no verificable.")
        return row[0]

    def abrir_hls(
        self, media_id: int, profile_id: int, video_root: str, cookie_fingerprint: str,
    ) -> tuple[str, int]:
        media, profile = _media(media_id), _profile(profile_id)
        root, fingerprint = _identity(video_root, cookie_fingerprint)
        ticket = secrets.token_hex(24)
        with self._transaction() as conn:
            if self._state(conn, media) != "libre":
                raise AdmisionRechazada("La película no admite nuevas sesiones.")
            generation = self._generation(conn, media)
            conn.execute(
                "INSERT INTO sesiones(token,media_id,abierta) VALUES (?,?,1)",
                (ticket, media),
            )
            conn.execute(
                "INSERT INTO propietarios(sesion,perfil_id) VALUES (?,?)",
                (ticket, profile),
            )
            conn.execute(
                "INSERT INTO sesiones_hls(sesion,video_root,huella_cookie,generacion) "
                "VALUES (?,?,?,?)",
                (ticket, root, fingerprint, generation),
            )
        return ticket, generation

    @staticmethod
    def _assert_hls(
        conn: sqlite3.Connection, media: int, profile: int, session: str,
        generation: int, root: str, fingerprint: str,
    ) -> None:
        if type(generation) is not int or not 0 < generation <= 2_147_483_647:
            raise AdmisionRechazada("Generación de sesión inválida.")
        row = conn.execute(
            "SELECT s.abierta FROM sesiones AS s "
            "JOIN propietarios AS p ON p.sesion=s.token "
            "JOIN sesiones_hls AS h ON h.sesion=s.token "
            "WHERE s.token=? AND s.media_id=? AND p.perfil_id=? "
            "AND h.generacion=? AND h.video_root=? AND h.huella_cookie=?",
            (session, media, profile, generation, root, fingerprint),
        ).fetchone()
        if row is None or row[0] != 1:
            raise AdmisionRechazada("Sesión HLS cerrada o ajena.")

    def reservar_lectura_hls(
        self, media_id: int, profile_id: int, session_id: str,
        generation: int, video_root: str, cookie_fingerprint: str,
    ) -> str:
        """Una transacción valida estado, generación, propietario y reserva."""
        media, profile, ticket = (
            _media(media_id), _profile(profile_id), _token(session_id),
        )
        root, fingerprint = _identity(video_root, cookie_fingerprint)
        request = secrets.token_hex(24)
        with self._transaction() as conn:
            if self._state(conn, media) != "libre":
                raise AdmisionRechazada("Drenaje o película no disponible.")
            if self._generation(conn, media) != generation:
                raise AdmisionRechazada("Capacidad HLS revocada.")
            self._assert_hls(
                conn, media, profile, ticket, generation, root, fingerprint,
            )
            conn.execute(
                "INSERT INTO solicitudes(token,sesion) VALUES (?,?)", (request, ticket),
            )
        return request

    def cerrar_hls(
        self, media_id: int, profile_id: int, session_id: str,
        generation: int, video_root: str, cookie_fingerprint: str,
    ) -> None:
        media, profile, ticket = (
            _media(media_id), _profile(profile_id), _token(session_id),
        )
        root, fingerprint = _identity(video_root, cookie_fingerprint)
        with self._transaction() as conn:
            self._assert_hls(
                conn, media, profile, ticket, generation, root, fingerprint,
            )
            conn.execute(
                "UPDATE sesiones SET abierta=0 WHERE token=?", (ticket,),
            )
            conn.execute(
                "DELETE FROM sesiones WHERE token=? AND NOT EXISTS("
                "SELECT 1 FROM solicitudes WHERE sesion=?)",
                (ticket, ticket),
            )
            self._update_finished(conn, media)

    def iniciar_drenaje(self, medio_id: int) -> dict:
        media = _media(medio_id)
        with self._transaction() as conn:
            state = self._state(conn, media)
            generation = self._generation(conn, media)
            if state == "libre":
                if generation == 2_147_483_647:
                    raise AdmisionRechazada("Generación agotada.")
                conn.execute(
                    "UPDATE generaciones_hls SET generacion=? WHERE media_id=?",
                    (generation + 1, media),
                )
                conn.execute(
                    "UPDATE peliculas SET estado='drenando' WHERE id=?", (media,),
                )
            self._update_finished(conn, media)
            state = self._state(conn, media)
        return {
            "estado": state,
            "no_hay_sesiones_viewtv": state == "listo_para_preflight",
            "jellyfin_externo_controlado": False,
            "qbit_controlado": False,
            "autoriza_borrado_fisico": False,
        }
