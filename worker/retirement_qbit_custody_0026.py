"""Custodia qBittorrent 0026: clasifica sin cambiar ni borrar torrents.

Un torrent marcado COMPLETO o PARADO no prueba que se pueda eliminar.
Todos los archivos qBit ajenos al diario se protegen, incluso metadatos de
tamaño diminuto. Solo retorna contadores; nunca rutas, hashes ni permisos.
"""
from __future__ import annotations

from collections import Counter
from pathlib import PureWindowsPath

from worker.retirement_inventory_0020 import _group
from worker.retirement_preflight_0018 import (
    HASH_RE,
    TORRENT_ROOT,
    _valid_relative,
)

RESTING_STATES = frozenset({"pausedUP", "stoppedUP"})
MAX_DOWNLOADS = 200
MAX_FILES = 100


class CustodiaNoConfiable(ValueError):
    """Rechazo por evidencia incompleta o identidad no coherente."""


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


def _progress(value: object) -> bool:
    return type(value) in (int, float) and 0 <= value <= 1


def _manifest(journal: tuple, download_id: int) -> dict[str, int]:
    if (
        not isinstance(journal, tuple)
        or len(journal) != 2
        or not isinstance(journal[0], dict)
        or journal[0].get("download_id") != download_id
        or not isinstance(journal[1], str)
        or len(journal[1]) != 64
    ):
        raise CustodiaNoConfiable("Diario de descarga no verificable.")
    record = journal[0]
    intent = record.get("intent")
    if not isinstance(intent, dict) or intent.get("download_id") != download_id:
        raise CustodiaNoConfiable("Identidad de diario inconsistente.")
    manifest = intent.get("files")
    if not isinstance(manifest, list) or not 1 <= len(manifest) <= 20:
        raise CustodiaNoConfiable("Archivo de publicación no verificable.")
    expected: dict[str, int] = {}
    for f in manifest:
        if not isinstance(f, dict):
            raise CustodiaNoConfiable("Archivo de publicación no verificable.")
        name, size = f.get("source_relative"), f.get("size_bytes")
        parts = _valid_relative(name)
        if parts is None or not _positive(size):
            raise CustodiaNoConfiable("Archivo del manifiesto inválido.")
        key = "/".join(parts).casefold()
        if key in expected:
            raise CustodiaNoConfiable("Manifiesto con archivos repetidos.")
        expected[key] = size
    return expected


def evaluar_custodia_qbit(snapshot: dict, journals: dict) -> dict:
    """Resumen agregado: nunca autoriza operación física o alteración qBit.

    Si una fuente no permite concluir nada, se aborta el informe completo.
    Los ficheros extra tampoco pueden excluirse por extensión, tamaño o
    prioridad aunque el torrent declare 100% de progreso.
    """
    if not isinstance(snapshot, dict) or not isinstance(journals, dict):
        raise CustodiaNoConfiable("Fuentes no verificables.")
    downloads = snapshot.get("descargas")
    torrents = snapshot.get("qbittorrent")
    if (
        not isinstance(downloads, list) or not isinstance(torrents, dict)
        or not 1 <= len(downloads) <= MAX_DOWNLOADS
        or len(torrents) != len(downloads)
    ):
        raise CustodiaNoConfiable("Inventario no completo.")
    ids: set[int] = set()
    counts = Counter({
        "descargas": 0,
        "torrent_completo_y_en_reposo_reportado": 0,
        "torrent_no_en_reposo_o_incompleto": 0,
        "torrent_propiedad_o_ruta_inconsistente": 0,
        "torrents_con_archivos_extra": 0,
        "archivos_qbit": 0,
        "archivos_publicados_correlacionados": 0,
        "archivos_extra_protegidos": 0,
        "extras_con_nombre_no_normalizable": 0,
        "extras_tipo_video": 0,
        "extras_tipo_subtitulo": 0,
        "extras_tipo_metadato": 0,
        "extras_tipo_otro": 0,
        "bytes_logicos_extras_protegidos": 0,
        "archivos_con_tamano_incompatible": 0,
        "archivos_con_progreso_incompleto": 0,
        "archivos_con_prioridad_excluida": 0,
    })
    for d in downloads:
        if not isinstance(d, dict) or not _positive(d.get("id")):
            raise CustodiaNoConfiable("Identidad de descarga no verificable.")
        download_id = d["id"]
        if download_id in ids:
            raise CustodiaNoConfiable("Descarga repetida.")
        ids.add(download_id)
        if download_id not in journals:
            raise CustodiaNoConfiable("Descarga sin diario.")
        expected = _manifest(journals[download_id], download_id)
        data = torrents.get(str(download_id))
        if (
            not isinstance(data, dict)
            or data.get("estado_consulta") != "ok"
            or not isinstance(data.get("torrent"), dict)
            or not isinstance(data.get("files"), list)
            or not 1 <= len(data["files"]) <= MAX_FILES
        ):
            raise CustodiaNoConfiable("Torrent no disponible.")
        t = data["torrent"]
        own = f"viewtv-descarga-{download_id}"
        tag_value = t.get("tags")
        tags = (
            [tag.strip() for tag in tag_value.split(",")]
            if isinstance(tag_value, str) else []
        )
        hash_ = d.get("hash")
        valid_hash = isinstance(hash_, str) and HASH_RE.fullmatch(hash_) is not None
        valid_identity = (
            valid_hash and isinstance(t.get("hash"), str)
            and t["hash"].casefold() == hash_.casefold()
            and isinstance(tag_value, str)
            and own in tags and len(tags) == len(set(tags))
            and all(
                not tag.startswith("viewtv-descarga-") or tag == own
                for tag in tags
            )
            and isinstance(t.get("save_path"), str)
            and str(PureWindowsPath(t["save_path"])).casefold()
            == str(TORRENT_ROOT).casefold()
            and journals[download_id][0].get("intent", {}).get("torrent_hash")
            == hash_
        )
        if not valid_identity:
            counts["torrent_propiedad_o_ruta_inconsistente"] += 1

        state = t.get("state")
        if not isinstance(state, str) or not state or not _progress(t.get("progress")):
            raise CustodiaNoConfiable("Estado qBit no reconocible.")
        at_rest = state in RESTING_STATES and t["progress"] == 1
        if at_rest:
            counts["torrent_completo_y_en_reposo_reportado"] += 1
        else:
            counts["torrent_no_en_reposo_o_incompleto"] += 1

        observed: set[str] = set()
        extra = 0
        for f in data["files"]:
            if not isinstance(f, dict) or not isinstance(f.get("name"), str):
                raise CustodiaNoConfiable("Nombre de archivo qBit no verificable.")
            normalized = f["name"].replace("\\", "/")
            size, prog, priority = f.get("size"), f.get("progress"), f.get("priority")
            if not _positive(size) or not _progress(prog):
                raise CustodiaNoConfiable("Tamaño o progreso de qBit inválido.")
            if type(priority) is not int or priority < 0:
                raise CustodiaNoConfiable("Prioridad qBit inválida.")
            key = normalized.casefold()
            if key in observed:
                raise CustodiaNoConfiable("Archivo qBit duplicado.")
            observed.add(key)
            counts["archivos_qbit"] += 1
            if prog != 1:
                counts["archivos_con_progreso_incompleto"] += 1
            if priority == 0:
                counts["archivos_con_prioridad_excluida"] += 1
            parts = _valid_relative(normalized)
            if key in expected and size == expected[key] and parts is not None:
                counts["archivos_publicados_correlacionados"] += 1
                continue
            if key in expected:
                counts["archivos_con_tamano_incompatible"] += 1
            extra += 1
            counts["archivos_extra_protegidos"] += 1
            counts["bytes_logicos_extras_protegidos"] += size
            counts["extras_tipo_" + _group(normalized)] += 1
            if parts is None:
                counts["extras_con_nombre_no_normalizable"] += 1
        if extra:
            counts["torrents_con_archivos_extra"] += 1
        counts["descargas"] += 1

    if set(journals) != ids or set(torrents) != {str(id_) for id_ in ids}:
        raise CustodiaNoConfiable("Diarios o torrents ajenos a la consulta.")
    result = dict(counts)
    result.update({
        "estado": "inventario_custodiado_sin_retirada",
        "ficheros_extra_conservados": True,
        "bloqueo_jellyfin_y_qbit_transaccional": False,
        "autoriza_borrado_fisico": False,
        "archivos_eliminados": 0,
        "torrents_modificados": 0,
    })
    return result
