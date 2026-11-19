"""Interpretación conservadora del estado de qBittorrent."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.database import engine
from app.models import Descarga
from app.qbittorrent import QBittorrentClient, QBittorrentError
from app.queue import update_download_progress
from sqlmodel import Session, select

logger = logging.getLogger("viewtv.download_monitor")


@dataclass(frozen=True)
class TorrentStatus:
    estado: str
    progreso: float
    tamano_bytes: int | None


def interpret_torrent(data: dict) -> TorrentStatus | None:
    """Convierte datos de qBittorrent a estados de VIEWTV.

    Devuelve None si el estado es desconocido o los datos no son válidos.
    No declara ningún archivo disponible en Jellyfin.
    """
    state = data.get("state")
    progress = data.get("progress")

    if not isinstance(state, str):
        return None

    if isinstance(progress, bool) or not isinstance(
        progress, (int, float)
    ):
        return None

    if not 0 <= progress <= 1:
        return None

    size = data.get("total_size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        size = None

    complete = progress >= 1

    if complete and state in {
        "stoppedDL", "stoppedUP", "uploading",
        "stalledUP", "queuedUP", "forcedUP", "checkingUP",
    }:
        estado = "completada"
    elif state in {"stoppedDL", "stoppedUP", "pausedDL", "pausedUP"}:
        estado = "pausada"
    elif state in {"downloading", "forcedDL", "stalledDL"}:
        estado = "descargando"
    elif state in {"metaDL", "queuedDL", "checkingDL", "checkingResumeData"}:
        estado = "enviada"
    else:
        return None

    return TorrentStatus(
        estado=estado,
        progreso=float(progress),
        tamano_bytes=size,
    )



def monitor_downloads_once(
    client: QBittorrentClient | None = None,
) -> int:
    """Consulta descargas de VIEWTV y sincroniza sus estados conocidos."""
    qbittorrent = client or QBittorrentClient()

    with Session(engine) as session:
        descargas = session.exec(
            select(Descarga).where(
                Descarga.estado.in_(
                    ["enviada", "descargando", "pausada"]
                ),
                Descarga.inicio_estado != "pendiente",
                Descarga.qbittorrent_hash.is_not(None),
            )
        ).all()

        pendientes = [
            (
                descarga.id,
                descarga.qbittorrent_hash,
                descarga.estado,
                descarga.inicio_estado,
                descarga.actualizado_en,
            )
            for descarga in descargas
        ]

    actualizadas = 0

    for (
        download_id,
        torrent_hash,
        estado_actual,
        inicio_estado,
        actualizado_en,
    ) in pendientes:
        if download_id is None or not torrent_hash:
            continue

        try:
            torrents = qbittorrent.torrents_info(
                hashes=[torrent_hash]
            )
        except QBittorrentError:
            logger.warning(
                "No se pudo consultar la descarga %s",
                download_id,
            )
            continue

        torrent = next(
            (
                item for item in torrents
                if isinstance(item.get("hash"), str)
                and item["hash"].lower() == torrent_hash.lower()
            ),
            None,
        )

        if torrent is None:
            continue

        estado = interpret_torrent(torrent)

        if estado is None:
            continue

        # qBittorrent puede seguir notificando stoppedDL unos instantes
        # después de aceptar el inicio. El margen solo se aplica antes
        # de observar actividad; una pausa posterior nunca se oculta.
        if (
            inicio_estado == "iniciada"
            and estado_actual == "enviada"
            and estado.estado == "pausada"
            and torrent.get("state") == "stoppedDL"
            and estado.progreso == 0
            and actualizado_en is not None
        ):
            fecha = actualizado_en
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=UTC)
            edad = datetime.now(UTC) - fecha
            if timedelta(0) <= edad < timedelta(seconds=90):
                continue

        with Session(engine) as session:
            changed = update_download_progress(
                session,
                download_id,
                torrent_hash,
                estado.estado,
                estado.progreso,
                estado.tamano_bytes,
            )

        if changed:
            actualizadas += 1

    return actualizadas
