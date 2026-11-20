"""Procesamiento de descargas seleccionadas por el usuario."""

import logging
import re
from pathlib import PureWindowsPath
from urllib.parse import urlsplit, urlunsplit

from app.database import engine
from app.config import get_settings
from app.models import ResultadoBusqueda
from app.qbittorrent import (
    QBittorrentAddPending,
    QBittorrentClient,
    QBittorrentError,
)
from app.queue import (
    claim_next_download,
    fail_download,
    mark_download_submitted,
    record_download_attempt,
)
from sqlmodel import Session, select

logger = logging.getLogger("viewtv.worker.download_processor")

# Mismo destino exigido por el iniciador de VIEWTV; nunca se crea aquí.
STAGING_PATH = r"C:\VIEWTV\media\descargas_temporales"


def _qbit_url_for_windows_jackett(url: str, jackett_base_url: str) -> str:
    """Convierte SOLO la URL interna Jackett a loopback para qBit Windows.

    El contenedor resuelve host.docker.internal, pero qBittorrent
    ejecutado en Windows no. No reescribe dominios externos, enlaces
    magnet, orígenes diferentes ni rutas distintas de /dl/.
    """
    parsed = urlsplit(url)
    jackett = urlsplit(jackett_base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "host.docker.internal"
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/dl/")
        or jackett.scheme != parsed.scheme
        or jackett.hostname != parsed.hostname
        or jackett.port is None
        or parsed.port != jackett.port
    ):
        return url
    return urlunsplit(
        parsed._replace(netloc=f"127.0.0.1:{jackett.port}")
    )


PENDING_ADD_MARKER = "Alta asíncrona pendiente en qBittorrent; no reenviar."


class TrialAdmissionError(QBittorrentError):
    """El torrent no tiene la identidad, ruta o estado seguro esperados."""


def _trial_torrent_hash(torrents: list[dict], tag: str) -> str | None:
    """Exige un único torrent detenido, etiquetado y en staging correcto."""
    if not torrents:
        return None
    if len(torrents) != 1:
        raise TrialAdmissionError("No hay una coincidencia única de la etiqueta.")
    torrent = torrents[0]
    value = torrent.get("hash")
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value) is None
    ):
        raise TrialAdmissionError("Hash de torrent no válido.")
    tags = torrent.get("tags")
    if not isinstance(tags, str) or tag not in {
        part.strip() for part in tags.split(",")
    }:
        raise TrialAdmissionError("La etiqueta del torrent no coincide.")
    path = torrent.get("save_path")
    if not isinstance(path, str) or ".." in PureWindowsPath(path).parts:
        raise TrialAdmissionError("Ruta del torrent no autorizada.")
    if str(PureWindowsPath(path)).casefold() != STAGING_PATH.casefold():
        raise TrialAdmissionError("El torrent está fuera del staging permitido.")
    if torrent.get("state") not in {"stoppedDL", "stoppedUP", "pausedDL", "pausedUP"}:
        raise TrialAdmissionError("El torrent no está detenido.")
    return value.lower()


def _torrent_hash(torrents: list[dict]) -> str | None:
    """Obtiene un hash válido de la respuesta de qBittorrent."""
    for torrent in torrents:
        value = torrent.get("hash")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def _record_failure(
    download_id: int,
    worker_id: str,
    message: str,
    *,
    permanent: bool = False,
) -> None:
    with Session(engine) as session:
        failed = fail_download(
            session,
            download_id,
            worker_id,
            message,
            permanent=permanent,
        )

    if not failed:
        logger.warning(
            "No se pudo registrar el fallo de la descarga %s: lease perdido",
            download_id,
        )


def process_one_download(
    worker_id: str,
    client: QBittorrentClient | None = None,
    *,
    allowed_download_id: int | None = None,
    save_path: str | None = None,
) -> bool:
    """Ensayo acotado: filtra ID y destino antes de reclamar una descarga."""
    if allowed_download_id is not None and save_path != STAGING_PATH:
        raise ValueError("La ruta de staging autorizada no coincide")

    with Session(engine) as session:
        download = claim_next_download(
            session, worker_id, allowed_download_id=allowed_download_id
        )

        if download is None:
            return False

        download_id = download.id
        request_id = download.solicitud_id
        result_id = download.resultado_busqueda_id
        attempts = download.intentos_envio
        max_attempts = download.max_intentos_envio
        previous_pending = download.ultimo_error == PENDING_ADD_MARKER

        result = None
        if result_id is not None:
            result = session.exec(
                select(ResultadoBusqueda).where(
                    ResultadoBusqueda.id == result_id,
                    ResultadoBusqueda.solicitud_id == request_id,
                )
            ).first()

        magnet_url = result.magnet_url if result else None
        download_url = result.download_url if result else None

    if download_id is None:
        return True

    # La selección debe apuntar a un resultado de la misma solicitud.
    if result is None:
        _record_failure(
            download_id,
            worker_id,
            "No se encuentra el resultado de búsqueda seleccionado.",
            permanent=True,
        )
        return True

    # Preferimos el magnet; usamos la URL torrent como alternativa.
    torrent_url = magnet_url or download_url
    if (
        allowed_download_id is not None
        and magnet_url is None
        and torrent_url
    ):
        # El enlace /dl/ de Jackett es válido desde Docker, pero el
        # qBittorrent Windows necesita el mismo servicio por loopback.
        torrent_url = _qbit_url_for_windows_jackett(
            torrent_url, get_settings().jackett_base_url
        )
    if not torrent_url or not torrent_url.strip():
        _record_failure(
            download_id,
            worker_id,
            "El resultado seleccionado no tiene un enlace utilizable.",
            permanent=True,
        )
        return True

    tag = f"viewtv-descarga-{download_id}"

    try:
        qbittorrent = client or QBittorrentClient()

        # Primero reconciliamos: el envío pudo completarse antes de
        # que un worker anterior perdiera su lease o se interrumpiera.
        existing = qbittorrent.torrents_info(tag=tag)
        existing_hash = (
            _trial_torrent_hash(existing, tag)
            if allowed_download_id is not None
            else _torrent_hash(existing)
        )

        if existing:
            if existing_hash is None:
                raise QBittorrentError(
                    "qBittorrent encontró la etiqueta, pero no devolvió su hash."
                )

            with Session(engine) as session:
                saved = mark_download_submitted(
                    session,
                    download_id,
                    worker_id,
                    existing_hash,
                )

            if not saved:
                logger.warning(
                    "Lease perdido al reconciliar la descarga %s",
                    download_id,
                )
            else:
                logger.info(
                    "Descarga %s ya estaba en qBittorrent; envío reconciliado",
                    download_id,
                )
            return True

        # HTTP 202 (qBittorrent 5.3): el alta ya está pendiente.
        # Si aún no aparece la etiqueta, consultar más tarde SIN
        # efectuar ningún segundo POST ni consumir otro intento.
        if previous_pending:
            _record_failure(download_id, worker_id, PENDING_ADD_MARKER)
            return True

        # Si ya se consumieron todos los intentos, no volvemos a enviar.
        if attempts >= max_attempts:
            _record_failure(
                download_id,
                worker_id,
                "No se encontró el torrent en qBittorrent tras agotar los intentos.",
            )
            return True

        # Consumimos el intento justo antes de llamar a qBittorrent.
        with Session(engine) as session:
            recorded = record_download_attempt(
                session,
                download_id,
                worker_id,
            )

        if not recorded:
            logger.warning(
                "No se pudo consumir un intento para la descarga %s",
                download_id,
            )
            return True

        add_error: QBittorrentError | None = None
        try:
            qbittorrent.add_torrent(
                torrent_url,
                tags=[tag],
                stopped=True,
                **({"save_path": save_path} if allowed_download_id is not None else {}),
            )
        except QBittorrentAddPending:
            # El POST 202 puede materializarse después; nunca duplicarlo.
            add_error = QBittorrentAddPending(PENDING_ADD_MARKER)
        except QBittorrentError as error:
            # Una respuesta ambigua no garantiza que el alta fallara.
            add_error = error

        # Confirmamos mediante la etiqueta, no suponiendo que el alta
        # HTTP equivale a que el torrent ya esté registrado.
        submitted = qbittorrent.torrents_info(tag=tag)
        torrent_hash = (
            _trial_torrent_hash(submitted, tag)
            if allowed_download_id is not None
            else _torrent_hash(submitted)
        )

        if torrent_hash is None:
            if add_error is not None:
                raise add_error
            raise QBittorrentError(
                "qBittorrent aceptó el envío, pero todavía no aparece "
                "el torrent con su etiqueta."
            )

        with Session(engine) as session:
            saved = mark_download_submitted(
                session,
                download_id,
                worker_id,
                torrent_hash,
            )

        if saved:
            logger.info(
                "Descarga %s enviada a qBittorrent",
                download_id,
            )
        else:
            logger.warning(
                "Lease perdido al confirmar la descarga %s",
                download_id,
            )

    except Exception as error:
        logger.exception(
            "Error procesando la descarga %s",
            download_id,
        )

        message = (
            str(error)
            if isinstance(error, QBittorrentError)
            else f"Error interno: {error.__class__.__name__}"
        )

        try:
            _record_failure(
                download_id,
                worker_id,
                message,
                permanent=isinstance(error, TrialAdmissionError),
            )
        except Exception:
            logger.exception(
                "No se pudo registrar el fallo de la descarga %s",
                download_id,
            )

    return True
