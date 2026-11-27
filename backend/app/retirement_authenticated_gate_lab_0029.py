"""0029: integración HTTP POST-AUTENTICACIÓN, solo importada por tests.

NO se instala en app.main. Utiliza get_current_profile real (cookie JWT
+ perfil activo verificado por SQLModel), antes de consultar si una película
está en drenaje. Denegar a anónimos siempre 401, incluso en drenaje.

Registro transaccional de cada solicitud asociado al perfil en SQLite
TEMP GUID de laboratorio 0027/0029; NO protege enlaces HLS frente a
transferencia entre perfiles, acceso directo a Jellyfin o qBittorrent.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session
from starlette.requests import Request
from worker.retirement_playback_admission_0027 import AdmisionRechazada
from worker.retirement_profile_admission_0029 import AdmisionPerfilLab0029

from app.auth import get_current_profile
from app.retirement_http_gate_lab_0028 import StreamingRouteGuardLab0028


class VerificadorPerfilLab0029:
    """Aplica la función de auth REAL con una DB de perfiles de pruebas.

    session_factory se suministra solamente desde los tests y apunta a
    una base EN MEMORIA; jamás busca automáticamente la DB de producción.
    No admite bypass de get_current_profile por un ID arbitrario.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        if not callable(session_factory):
            raise TypeError("Se necesita una fábrica de sesión de prueba.")
        self._factory = session_factory

    def __call__(self, scope: dict) -> int:
        with self._factory() as db:
            user = get_current_profile(Request(scope), db)
            if type(user.id) is not int or not 0 < user.id <= 2_147_483_647:
                raise ValueError("Perfil no verificable.")
            return user.id


class AuthenticatedPlaybackGateLab0029:
    """Guarda peticiones de vídeo solo tras validar cookie y perfil activo."""

    def __init__(
        self,
        app: Any,
        lab: AdmisionPerfilLab0029,
        verifier: VerificadorPerfilLab0029,
    ) -> None:
        if not isinstance(lab, AdmisionPerfilLab0029):
            raise TypeError("Se requiere una DB TEMP con dueño de sesión.")
        if not isinstance(verifier, VerificadorPerfilLab0029):
            raise TypeError("Se requiere autenticación de perfil real.")
        self.app, self.lab, self.verifier = app, lab, verifier

    @staticmethod
    async def _reply(send: Any, status: int) -> None:
        body = {
            401: b'{"detail":"Autenticacion necesaria."}',
            404: b'{"detail":"Ruta no disponible."}',
            423: b'{"detail":"Reproduccion temporalmente no disponible."}',
            503: b'{"detail":"Servicio de reproduccion no disponible."}',
        }[status]
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"private, no-store"),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        action, media_id = StreamingRouteGuardLab0028._target(scope)
        if action == "other":
            await self.app(scope, receive, send)
            return

        # La verificación de identidad ocurre ANTES de leer estado de
        # drenaje, del tipo de ruta o de abrir el registro de streaming.
        try:
            profile_id = self.verifier(scope)
        except HTTPException:
            await self._reply(send, 401)
            return
        except (OSError, ValueError, TypeError, sqlite3.Error):
            await self._reply(send, 503)
            return

        if action != "video" or media_id is None:
            await self._reply(send, 404)
            return

        ticket: str | None = None
        io: str | None = None
        try:
            ticket = self.lab.abrir_para_perfil(media_id, profile_id)
            io = self.lab.empezar_lectura(media_id, profile_id, ticket)
        except (AdmisionRechazada, OSError, sqlite3.Error, ValueError):
            if ticket is not None:
                try:
                    self.lab.cerrar_para_perfil(media_id, profile_id, ticket)
                except (AdmisionRechazada, OSError, sqlite3.Error):
                    pass
            await self._reply(send, 423)
            return

        # Señal de admisión emitida únicamente TRAS autenticar y reservar
        # lectura en la SQLite TEMP. Nunca confiar en cabeceras del cliente.
        scope["viewtv.retirement.admitted_0029"] = True
        try:
            await self.app(scope, receive, send)
        finally:
            if io is not None:
                try:
                    self.lab.terminar_lectura(media_id, profile_id, ticket, io)
                except (AdmisionRechazada, OSError, sqlite3.Error):
                    # Crash/DB error => fila retenida y drenaje bloqueado.
                    pass
            if ticket is not None:
                try:
                    self.lab.cerrar_para_perfil(media_id, profile_id, ticket)
                except (AdmisionRechazada, OSError, sqlite3.Error):
                    pass
