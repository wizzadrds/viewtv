"""0032: contrato de inyección HLS para probar las rutas reales sin despliegue.

La dependencia de FastAPI devuelve None mientras la autoridad de drenaje
productiva no esté implementada y validada. Un puente de laboratorio NO
debe registrarse en app.main ni ser promovido a la API en uso.
"""
from __future__ import annotations

from typing import Protocol

from fastapi import Request

from app.config import Settings
from app.models import Perfil


class HLSAdmissionClosed0032(Exception):
    """Una película no admite nuevas sesiones ni nuevas lecturas."""


class HLSBridge0032(Protocol):
    def require_admitted(self, request: Request) -> None: ...

    def issue(
        self, uri: str, media_id: int, profile: Perfil,
        request: Request, settings: Settings,
    ) -> str: ...

    def reserve(
        self, token: str, media_id: int, profile: Perfil,
        request: Request, settings: Settings,
    ) -> tuple[str, object]: ...

    def rewrite(
        self, contents: bytes, upstream_uri: str,
        lease: object, settings: Settings,
    ) -> bytes: ...

    def finish(self, lease: object) -> None: ...


def get_hls_bridge_0032() -> HLSBridge0032 | None:
    """La API actual sigue con HLS v1; no hay despliegue de 0031/0032."""
    return None
