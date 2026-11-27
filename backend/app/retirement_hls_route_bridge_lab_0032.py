"""0032: adapta capacidad HLS 0031 a las rutas FastAPI reales, SOLO TESTS.

No se registra en app.main, no abre servicios reales ni crea permisos de
retirada. La inyección de este adaptador se limita a TestClient sobre
SQLite TEMP marcada y el ASGI autenticado del laboratorio 0029.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from worker.retirement_hls_session_lab_0031 import AdmisionHLSLab0031
from worker.retirement_playback_admission_0027 import AdmisionRechazada

from app.config import Settings
from app.jellyfin import JellyfinError
from app.jellyfin_hls import _safe_upstream_url
from app.models import Perfil
from app.retirement_hls_bridge_contract_0032 import HLSAdmissionClosed0032
from app.retirement_hls_capability_lab_0031 import (
    HLSContext0031,
    cookie_fingerprint_0031,
    local_hls_v2_0031,
    rewrite_hls_v2_0031,
    verify_hls_v2_0031,
)


@dataclass(frozen=True)
class HLSLeaseLab0032:
    media_id: int
    profile_id: int
    cookie: str
    session_id: str
    generation: int
    video_root: str
    fingerprint: str
    io: str


class HLSRouteBridgeLab0032:
    """Controla emisión, reserva, reescritura y cierre de streaming HLS."""

    def __init__(self, lab: AdmisionHLSLab0031, settings: Settings) -> None:
        if not isinstance(lab, AdmisionHLSLab0031):
            raise TypeError("Autoridad TEMP 0031 obligatoria.")
        self.lab = lab
        self.settings = settings

    def require_admitted(self, request: Request) -> None:
        if request.scope.get("viewtv.retirement.admitted_0029") is not True:
            raise HLSAdmissionClosed0032("No hay admisión ASGI verificada.")

    def _cookie(self, request: Request) -> str:
        self.require_admitted(request)
        cookie = request.cookies.get(self.settings.auth_cookie_name)
        if not cookie:
            raise JellyfinError("Se requiere un login activo.")
        return cookie

    def issue(
        self, uri: str, media_id: int, profile: Perfil,
        request: Request, settings: Settings,
    ) -> str:
        if settings != self.settings:
            raise JellyfinError("Configuración incompatible.")
        cookie = self._cookie(request)
        fingerprint = cookie_fingerprint_0031(cookie, profile.id, settings)
        path, _query = _safe_upstream_url(uri, settings.jellyfin_base_url)
        parts = path.split("/")
        if len(parts) < 4 or not parts[2]:
            raise JellyfinError("Vídeo HLS no verificable.")
        root = parts[2]
        # Revalida la raíz antes de escribir ninguna sesión nueva.
        preliminary = HLSContext0031(
            media_id, profile.id, "0" * 48, 1, root, cookie,
        )
        # Una ruta maliciosa no debe crear sesiones bloqueantes.
        local_hls_v2_0031(uri, preliminary, settings)
        try:
            ticket, generation = self.lab.abrir_hls(
                media_id, profile.id, root, fingerprint,
            )
        except AdmisionRechazada as exc:
            raise HLSAdmissionClosed0032() from exc
        actual = HLSContext0031(
            media_id, profile.id, ticket, generation, root, cookie,
        )
        return local_hls_v2_0031(uri, actual, settings)

    def reserve(
        self, token: str, media_id: int, profile: Perfil,
        request: Request, settings: Settings,
    ) -> tuple[str, HLSLeaseLab0032]:
        if settings != self.settings:
            raise JellyfinError("Configuración incompatible.")
        cookie = self._cookie(request)
        verified = verify_hls_v2_0031(
            token, media_id, profile.id, cookie, settings,
        )
        try:
            io = self.lab.reservar_lectura_hls(
                media_id, profile.id, verified.session_id,
                verified.generation, verified.video_root,
                verified.cookie_fingerprint,
            )
        except AdmisionRechazada as exc:
            raise HLSAdmissionClosed0032() from exc
        return verified.uri, HLSLeaseLab0032(
            media_id, profile.id, cookie, verified.session_id,
            verified.generation, verified.video_root,
            verified.cookie_fingerprint, io,
        )

    def rewrite(
        self, contents: bytes, upstream_uri: str,
        lease: HLSLeaseLab0032, settings: Settings,
    ) -> bytes:
        if settings != self.settings:
            raise JellyfinError("Configuración incompatible.")
        context = HLSContext0031(
            lease.media_id, lease.profile_id, lease.session_id,
            lease.generation, lease.video_root, lease.cookie,
        )
        return rewrite_hls_v2_0031(contents, upstream_uri, context, settings)

    def finish(self, lease: HLSLeaseLab0032) -> None:
        # Si falla SQLite, NO borrar la fila: permanecerá bloqueante.
        self.lab.terminar_lectura(
            lease.media_id, lease.profile_id, lease.session_id, lease.io,
        )

    def close_session(
        self, media_id: int, profile: Perfil,
        request: Request, session_id: str, generation: int, video_root: str,
    ) -> None:
        cookie = self._cookie(request)
        fingerprint = cookie_fingerprint_0031(cookie, profile.id, self.settings)
        self.lab.cerrar_hls(
            media_id, profile.id, session_id, generation,
            video_root, fingerprint,
        )
