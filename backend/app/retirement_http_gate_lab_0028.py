"""0028: prototipo ASGI de control de peticiones de VIDEO en laboratorio.

¡NO REGISTRADO EN app.main! No modifica la API activa, Jellyfin ni qBit.
Solo acepta LaboratorioAdmision0027: DB TEMP GUID sin permisos de medios.

Bloquea las tres rutas conocidas (negociación, stream y cada petición HLS)
al comenzar el drenaje. Conserva cada solicitud en vuelo hasta que el
coroutine ASGI finaliza, incluido el streaming del cuerpo de la respuesta.
No sustituye autenticación, sesión HLS ligada al perfil, control externo de
Jellyfin ni una barrera física de retirada. NO concede permiso de borrar.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any

from worker.retirement_playback_admission_0027 import (
    AdmisionRechazada,
    LaboratorioAdmision0027,
)

PLAYBACK_ROUTE = re.compile(
    r"/jellyfin/media/([1-9][0-9]{0,9})/(playback-info|stream|hls)\Z",
)
IMAGE_ROUTE = re.compile(
    r"/jellyfin/media/([1-9][0-9]{0,9})/images/(primary|backdrop)\Z",
)
MEDIA_PREFIX = "/jellyfin/media/"
DENIED = b'{"detail":"Reproduccion en revision. Intentalo mas tarde."}'
STATUS_LOCKED = 423
ALLOWED_METHODS = {
    "playback-info": "POST",
    "stream": "GET",
    "hls": "GET",
}


class StreamingRouteGuardLab0028:
    """Envoltorio ASGI que se instala explícitamente SOLO en los tests.

    Se crea un ticket por petición (incluidas playlists y segmentos).
    El ticket se adquiere ANTES de ejecutar el manejador ASGI,
    no se libera hasta que finaliza su streaming o se cancela.
    """

    def __init__(self, app: Any, lab: LaboratorioAdmision0027) -> None:
        if not isinstance(lab, LaboratorioAdmision0027):
            raise TypeError("Solo se admite un laboratorio TEMP verificado.")
        self.app = app
        self.lab = lab

    @staticmethod
    def _target(scope: dict) -> tuple[str, int | None]:
        if scope.get("type") != "http":
            return "other", None
        path, method = scope.get("path"), scope.get("method")
        if not isinstance(path, str) or not path.startswith(MEDIA_PREFIX):
            return "other", None

        # El proxy debe entregar el path canónico. Si el ASGI recibe
        # codificaciones alternativas o un path con ambigüedad, denegar.
        raw = scope.get("raw_path")
        if not isinstance(raw, bytes):
            return "blocked", None
        try:
            if raw != path.encode("ascii"):
                return "blocked", None
        except UnicodeEncodeError:
            return "blocked", None

        video = PLAYBACK_ROUTE.fullmatch(path)
        if video is not None:
            media = int(video[1])
            kind = video[2]
            if media > 2_147_483_647 or method != ALLOWED_METHODS[kind]:
                return "blocked", None
            return "video", media

        # Las imágenes no entregan video y deben seguir disponibles:
        # cualquier futura ruta de media desconocida falla cerrado
        # hasta auditar e incluirla explícitamente en esta barrera.
        images = IMAGE_ROUTE.fullmatch(path)
        if images is not None and method == "GET":
            return "other", None
        return "blocked", None

    @staticmethod
    async def _deny(send: Any) -> None:
        await send({
            "type": "http.response.start",
            "status": STATUS_LOCKED,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(DENIED)).encode("ascii")),
                (b"cache-control", b"private, no-store"),
            ],
        })
        await send({"type": "http.response.body", "body": DENIED})

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        action, media_id = self._target(scope)
        if action == "other":
            await self.app(scope, receive, send)
            return
        if action == "blocked" or media_id is None:
            await self._deny(send)
            return

        session: str | None = None
        io: str | None = None
        try:
            # Los dos actos se realizan ANTES del handler upstream.
            # Si comienza drenaje entre ellos, la sesión existente
            # queda contabilizada y acabará limpia en el finally.
            session = self.lab.abrir_sesion(media_id)
            io = self.lab.iniciar_peticion(media_id, session)
        except (AdmisionRechazada, sqlite3.Error, OSError, ValueError):
            # Una admisión parcial se deja conservadoramente contabilizada
            # si no puede cerrarse; nunca se convierte en permiso de borrar.
            if session is not None:
                try:
                    self.lab.cerrar_sesion(media_id, session)
                except (AdmisionRechazada, sqlite3.Error, OSError):
                    pass
            await self._deny(send)
            return

        try:
            await self.app(scope, receive, send)
        finally:
            # Tras fallos de IO o DB una sesión puede quedar registrada
            # para reconciliación supervisada; no se ignora para drenar.
            if io is not None:
                try:
                    self.lab.terminar_peticion(media_id, session, io)
                except (AdmisionRechazada, sqlite3.Error, OSError):
                    pass
            if session is not None:
                try:
                    self.lab.cerrar_sesion(media_id, session)
                except (AdmisionRechazada, sqlite3.Error, OSError):
                    pass
