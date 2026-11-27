"""0029 — vinculación de cada petición de vídeo al perfil EN LABORATORIO.

Extiende el protocolo 0027 con una tabla de dueño inmutable. El mismo
BEGIN IMMEDIATE inserta sesión + perfil, evitando sesiones sin dueño
visibles en el registro. Solo acepta la base privada TEMP del laboratorio;
ni autoriza retirada ni interviene en la base de producción.

Las sesiones se mantienen hasta acabar TODAS sus solicitudes. El dueño
no puede ser sustituido por otro perfil ni rescatar un stream ajeno.
"""
from __future__ import annotations

import secrets

from worker.retirement_playback_admission_0027 import (
    AdmisionRechazada,
    LaboratorioAdmision0027,
    _media,
    _token,
)


def _profile(profile_id: object) -> int:
    if type(profile_id) is not int or not 0 < profile_id <= 2_147_483_647:
        raise AdmisionRechazada("Identidad de perfil no verificable.")
    return profile_id


class AdmisionPerfilLab0029(LaboratorioAdmision0027):
    """Leases atribuidas a perfiles sin exponer sus IDs en los informes."""

    def __init__(self, root):
        super().__init__(root)
        with self._transaction() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS propietarios ("
                "sesion TEXT PRIMARY KEY REFERENCES sesiones(token) "
                "ON DELETE CASCADE, "
                "perfil_id INTEGER NOT NULL CHECK (perfil_id > 0))"
            )

    @staticmethod
    def _assert_owner(conn, media_id: int, perfil_id: int, token: str) -> int:
        row = conn.execute(
            "SELECT s.abierta FROM sesiones AS s "
            "JOIN propietarios AS p ON p.sesion=s.token "
            "WHERE s.token=? AND s.media_id=? AND p.perfil_id=?",
            (token, media_id, perfil_id),
        ).fetchone()
        if row is None or row[0] not in (0, 1):
            raise AdmisionRechazada("Sesión de perfil no reconocida.")
        return row[0]

    def abrir_para_perfil(self, media_id: int, perfil_id: int) -> str:
        media, profile = _media(media_id), _profile(perfil_id)
        token = secrets.token_hex(24)
        with self._transaction() as conn:
            if self._state(conn, media) != "libre":
                raise AdmisionRechazada("La película está en drenaje.")
            conn.execute(
                "INSERT INTO sesiones(token,media_id,abierta) VALUES (?, ?, 1)",
                (token, media),
            )
            conn.execute(
                "INSERT INTO propietarios(sesion,perfil_id) VALUES (?, ?)",
                (token, profile),
            )
        return token

    def empezar_lectura(self, media_id: int, perfil_id: int, session: str) -> str:
        media, profile, token = _media(media_id), _profile(perfil_id), _token(session)
        io = secrets.token_hex(24)
        with self._transaction() as conn:
            if self._state(conn, media) not in ("libre", "drenando"):
                raise AdmisionRechazada("Lecturas nuevas denegadas.")
            if self._assert_owner(conn, media, profile, token) != 1:
                raise AdmisionRechazada("Sesión finalizada.")
            conn.execute(
                "INSERT INTO solicitudes(token,sesion) VALUES (?, ?)", (io, token),
            )
        return io

    def terminar_lectura(
        self, media_id: int, perfil_id: int, session: str, io: str,
    ) -> None:
        media, profile = _media(media_id), _profile(perfil_id)
        token, request = _token(session), _token(io)
        with self._transaction() as conn:
            opened = self._assert_owner(conn, media, profile, token)
            if conn.execute(
                "SELECT 1 FROM solicitudes WHERE sesion=? AND token=?",
                (token, request),
            ).fetchone() is None:
                raise AdmisionRechazada("Lectura ajena o ya cerrada.")
            conn.execute("DELETE FROM solicitudes WHERE token=?", (request,))
            if opened == 0:
                conn.execute(
                    "DELETE FROM sesiones WHERE token=? AND NOT EXISTS("
                    "SELECT 1 FROM solicitudes WHERE sesion=?)",
                    (token, token),
                )
            self._update_finished(conn, media)

    def cerrar_para_perfil(self, media_id: int, perfil_id: int, session: str) -> None:
        media, profile, token = _media(media_id), _profile(perfil_id), _token(session)
        with self._transaction() as conn:
            if self._assert_owner(conn, media, profile, token) != 1:
                raise AdmisionRechazada("Sesión cerrada.")
            conn.execute("UPDATE sesiones SET abierta=0 WHERE token=?", (token,))
            conn.execute(
                "DELETE FROM sesiones WHERE token=? AND NOT EXISTS("
                "SELECT 1 FROM solicitudes WHERE sesion=?)",
                (token, token),
            )
            self._update_finished(conn, media)

    def observar_agregado(self, media_id: int) -> dict:
        """Sin nombres, tokens, IDs de sesión ni IDs de perfil."""
        observed = self.observar(media_id)
        return {
            "estado": observed["estado"],
            "sesiones_pendientes": observed["sesiones_viewtv_pendientes"],
            "peticiones_video_pendientes": observed["peticiones_video_pendientes"],
            "perfiles_identificados": True,
            "jellyfin_externo_controlado": False,
            "qbittorrent_controlado": False,
            "autoriza_borrado_fisico": False,
        }
