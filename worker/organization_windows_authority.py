"""Autoridad de preparación para publicador Windows 0013 (sin escritura de medios).

Esta capa no publica desde Docker. Limita los claims al corte histórico,
revalida lease y torrent, y entrega solo rutas *relativas* al broker Windows.
No se integra con worker/main.py ni está habilitada en producción 0012.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.models import Descarga, Solicitud
from app.organization_queue import claim_next_organization
from app.qbittorrent import QBittorrentClient
from sqlmodel import Session

from worker.organization_planner import UnsafeOrganizationPlan, plan_verified_media
from worker.organization_torrent_guard import verify_organization_torrent_identity

BROKER_ID = "publicador-windows-0013"
MAX_SQLITE_ID = 2**63 - 1


@dataclass(frozen=True)
class WindowsPublicationPolicy:
    mode: str
    after_id: int
    allowed_id: int | None = None


def _parse_id(value: str | None, *, allow_zero: bool = False) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError("Identificador de publicación inválido.")
    number = int(value)
    if number >= MAX_SQLITE_ID or number < (0 if allow_zero else 1):
        raise ValueError("Identificador de publicación fuera de rango.")
    return number


def publication_policy(env: Mapping[str, str]) -> WindowsPublicationPolicy:
    """Falla cerrado. El modo general necesita un opt-in independiente."""
    mode = env.get("VIEWTV_WINDOWS_PUBLICATION_MODE", "disabled")
    if mode == "disabled":
        return WindowsPublicationPolicy(mode="disabled", after_id=0)
    if mode not in {"single", "general"}:
        raise ValueError("Modo de publicación inválido.")
    after_id = _parse_id(env.get("VIEWTV_WINDOWS_PUBLICATION_AFTER_ID"), allow_zero=True)
    if mode == "single":
        allowed_id = _parse_id(env.get("VIEWTV_WINDOWS_PUBLICATION_DOWNLOAD_ID"))
        if allowed_id <= after_id:
            raise ValueError("La ID autorizada pertenece al histórico excluido.")
        return WindowsPublicationPolicy(mode, after_id, allowed_id)
    if env.get("VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED") != "true":
        raise ValueError("Falta aprobación explícita del modo general.")
    if after_id < 1:
        raise ValueError("El modo general exige un corte histórico positivo.")
    return WindowsPublicationPolicy(mode, after_id)


def claim_for_windows(
    session: Session,
    policy: WindowsPublicationPolicy,
    *,
    now: datetime | None = None,
) -> Descarga | None:
    if policy.mode == "disabled":
        return None
    if policy.mode not in {"single", "general"}:
        raise ValueError("Política no válida.")
    return claim_next_organization(
        session,
        BROKER_ID,
        allowed_download_id=policy.allowed_id,
        min_download_id=policy.after_id,
        now=now,
    )


def _utc(value: datetime | None) -> datetime:
    if not isinstance(value, datetime):
        raise UnsafeOrganizationPlan("Falta vencimiento de lease.")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def verify_windows_publication_sources(
    download: Descarga,
    qbittorrent: QBittorrentClient,
    *,
    staging_root: Path = Path("/media/descargas_temporales"),
    now: datetime | None = None,
) -> list[dict]:
    """Reconciliación sin planificar otra vez un destino que ya existe."""
    current = (now or datetime.now(UTC)).astimezone(UTC)
    expires = _utc(download.organizacion_locked_until)
    if (
        not isinstance(download.id, int)
        or download.id < 1
        or download.organizacion_locked_by != BROKER_ID
        or not isinstance(download.organizacion_intentos, int)
        or not 1 <= download.organizacion_intentos <= 3
        or expires <= current + timedelta(seconds=10)
        or download.estado != "completada"
        or download.progreso != 1
        or download.estado_verificacion != "verificada"
        or download.verificada_en is None
        or download.organizacion_estado != "pendiente"
    ):
        raise UnsafeOrganizationPlan("El lease de publicación no está vigente.")
    sources = verify_organization_torrent_identity(qbittorrent, download, staging_root)
    root = staging_root.resolve(strict=True)
    return [
        {
            "source_relative": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
        }
        for path in sources
    ]


def build_windows_publication_intent(
    download: Descarga,
    request: Solicitud,
    qbittorrent: QBittorrentClient,
    *,
    staging_root: Path = Path("/media/descargas_temporales"),
    media_root: Path = Path("/media"),
    now: datetime | None = None,
) -> dict:
    """Crea un contrato inmutable de lectura para un único claim vigente.

    El broker Windows debe verificar de nuevo el estado antes de publicar.
    El contrato no es autorización criptográfica ni orden de copiar.
    """
    current = (now or datetime.now(UTC)).astimezone(UTC)
    expires = _utc(download.organizacion_locked_until)
    if (
        not isinstance(download.id, int)
        or download.id < 1
        or not isinstance(download.organizacion_intentos, int)
        or not 1 <= download.organizacion_intentos <= 3
        or download.organizacion_locked_by != BROKER_ID
        or expires <= current + timedelta(seconds=10)
        or download.estado != "completada"
        or download.progreso != 1
        or download.estado_verificacion != "verificada"
        or download.verificada_en is None
        or download.organizacion_estado != "pendiente"
        or request.id != download.solicitud_id
    ):
        raise UnsafeOrganizationPlan("La descarga no tiene un lease válido de publicación.")

    source_files = verify_organization_torrent_identity(
        qbittorrent, download, staging_root
    )
    plan = plan_verified_media(download, request, source_files, staging_root, media_root)
    if plan.library != "Peliculas":
        # Primera fase: solo películas nuevas. Series posteriores requieren
        # reglas de reconciliación distintas para temporadas existentes.
        raise UnsafeOrganizationPlan("Esta fase admite solo películas nuevas.")
    records = []
    for item in plan.entries:
        try:
            origin = item.source.relative_to(staging_root.resolve(strict=True))
            target = item.destination.relative_to(media_root.resolve(strict=True))
        except ValueError:
            raise UnsafeOrganizationPlan("Ruta fuera de las raíces configuradas.") from None
        if not origin.parts or not target.parts or target.parts[0] != "Peliculas":
            raise UnsafeOrganizationPlan("Ruta no autorizada para Windows.")
        if item.size_bytes <= 0:
            raise UnsafeOrganizationPlan("Tamaño inválido.")
        records.append({
            "source_relative": origin.as_posix(),
            "destination_relative": target.as_posix(),
            "size_bytes": item.size_bytes,
        })
    if not records or len(records) > 20:
        raise UnsafeOrganizationPlan("Cantidad de archivos inválida.")
    return {
        "version": 1,
        "download_id": download.id,
        "worker_id": BROKER_ID,
        "attempt": download.organizacion_intentos,
        "torrent_hash": download.qbittorrent_hash,
        "lease_expires_utc": expires.isoformat(),
        "library": plan.library,
        "files": records,
    }
