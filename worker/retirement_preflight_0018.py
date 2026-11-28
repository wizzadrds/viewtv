"""Decisión de retirada estricta SIN efectos laterales (etapa 0018).

Une una instantánea SQLite/Jellyfin/qBit con manifiestos de publicación y
prueba Windows NTFS nativa, por HASH DEL DIARIO y descarga.id. NO autoriza
borrados: toda evaluación termina bloqueada sin autorización adicional del
administrador y reconciliación atómica en el ejecutor final.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import PurePosixPath, PureWindowsPath

HASH_RE = re.compile(r"(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})\Z")
SHA_RE = re.compile(r"[a-f0-9]{64}\Z")
LEAF_RE = re.compile(r"[A-Za-z0-9À-ÿ_.()\[\] +,'&-]{1,150}\Z")
RESERVED_WINDOWS_RE = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", re.IGNORECASE)
VIDEO_EXT = frozenset({".mkv", ".mp4", ".m4v", ".avi"})
SUB_EXT = frozenset({".srt", ".ass", ".vtt"})
TORRENT_ROOT = PureWindowsPath(r"C:\VIEWTV\media\descargas_temporales")


def _valid_relative(value: object) -> tuple[str, ...] | None:
    if (
        not isinstance(value, str)
        or not value or len(value) > 800
        or value.startswith("/") or "\\" in value or ":" in value
    ):
        return None
    parts = tuple(value.split("/"))
    if (
        not 1 <= len(parts) <= 16
        or any(
            p in (".", "..") or p.endswith(".") or p.strip() != p
            or LEAF_RE.fullmatch(p) is None
            or RESERVED_WINDOWS_RE.fullmatch(p.split(".", 1)[0]) is not None
            for p in parts
        )
    ):
        return None
    return parts


def _bool_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _torrent_reasons(download: dict, torrent_result: dict, files: list[dict]) -> list[str]:
    failures: list[str] = []
    if (
        download.get("estado") != "completada"
        or download.get("estado_verificacion") != "verificada"
        or download.get("organizacion_estado") != "organizada"
        or download.get("progreso") != 1
        or not download.get("verificada")
        or any(download.get(key) for key in (
            "organizacion_bloqueada", "verificacion_bloqueada", "inicio_bloqueado",
        ))
    ):
        failures.append("descarga_no_terminada_o_bloqueada")
    hash_ = download.get("hash")
    if not isinstance(hash_, str) or HASH_RE.fullmatch(hash_) is None:
        failures.append("hash_descarga_invalido")
        return failures
    if torrent_result.get("estado_consulta") != "ok":
        failures.append("torrent_no_verificable")
        return failures
    torrent = torrent_result.get("torrent")
    if not isinstance(torrent, dict):
        failures.append("torrent_no_verificable")
        return failures
    if not isinstance(torrent.get("hash"), str) or torrent["hash"].casefold() != hash_.casefold():
        failures.append("torrent_identidad_invalida")
    tag_value = torrent.get("tags")
    own_tag = f"viewtv-descarga-{download['id']}"
    if not isinstance(tag_value, str):
        failures.append("torrent_no_propio")
    else:
        tags = [tag.strip() for tag in tag_value.split(",")]
        if (
            own_tag not in tags or len(set(tags)) != len(tags)
            or any(
                tag.startswith("viewtv-descarga-") and tag != own_tag
                for tag in tags
            )
        ):
            failures.append("torrent_no_propio")
    path = torrent.get("save_path")
    if (
        not isinstance(path, str)
        or str(PureWindowsPath(path)).casefold() != str(TORRENT_ROOT).casefold()
    ):
        failures.append("torrent_raiz_ajena")
    state = torrent.get("state")
    if state not in ("pausedUP", "stoppedUP") or torrent.get("progress") != 1:
        failures.append("torrent_activo_o_incompleto")

    by_name: dict[str, int] = {}
    provided = torrent_result.get("files")
    if not isinstance(provided, list) or not 1 <= len(provided) <= 100:
        failures.append("torrent_archivos_no_verificables")
        return failures
    for item in provided:
        if not isinstance(item, dict):
            failures.append("torrent_archivos_no_verificables")
            break
        name = item.get("name")
        normalized = name.replace("\\", "/") if isinstance(name, str) else ""
        parts = _valid_relative(normalized)
        if (
            parts is None or not isinstance(item.get("size"), int)
            or isinstance(item["size"], bool) or item["size"] <= 0
            or item.get("progress") != 1
            or isinstance(item.get("priority"), bool)
            or (item.get("priority") is not None and (
                not isinstance(item["priority"], int) or item["priority"] <= 0
            ))
        ):
            failures.append("torrent_archivos_no_verificables")
            break
        key = "/".join(parts).casefold()
        if key in by_name:
            failures.append("torrent_archivos_duplicados")
            break
        by_name[key] = item["size"]
    journal_by_name: dict[str, int] = {}
    for item in files:
        if not isinstance(item, dict):
            failures.append("manifiesto_invalido")
            break
        parts = _valid_relative(item.get("source_relative"))
        size = item.get("size_bytes")
        if (
            parts is None or not _bool_int(size)
        ):
            failures.append("manifiesto_invalido")
            break
        key = "/".join(parts).casefold()
        if key in journal_by_name:
            failures.append("manifiesto_duplicado")
            break
        journal_by_name[key] = size
    if by_name != journal_by_name:
        failures.append("torrent_con_archivos_ajenos_o_incompletos")
    return failures


def _journal_match(record: dict, download: dict, path: str) -> list[str]:
    errors: list[str] = []
    intent = record.get("intent")
    if not isinstance(intent, dict):
        return ["manifiesto_invalido"]
    download_id = download.get("id")
    if (
        record.get("version") != 1
        or record.get("download_id") != download_id
        or intent.get("download_id") != download_id
        or intent.get("library") != "Peliculas"
        or intent.get("torrent_hash") != download.get("hash")
    ):
        errors.append("diario_no_coincide_descarga")
    folder = record.get("folder")
    if not isinstance(folder, str) or LEAF_RE.fullmatch(folder) is None or folder in (".", ".."):
        return errors + ["carpeta_diario_invalida"]
    files = intent.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= 20:
        return errors + ["manifiesto_invalido"]
    targets: set[str] = set()
    video: list[str] = []
    for f in files:
        if not isinstance(f, dict):
            errors.append("manifiesto_invalido")
            continue
        source = _valid_relative(f.get("source_relative"))
        dest = _valid_relative(f.get("destination_relative"))
        if (
            source is None or dest is None or len(dest) != 3
            or dest[0] != "Peliculas" or dest[1] != folder
            or not _bool_int(f.get("size_bytes"))
        ):
            errors.append("manifiesto_invalido")
            continue
        extension = PurePosixPath(dest[2]).suffix.lower()
        if extension not in VIDEO_EXT | SUB_EXT:
            errors.append("tipo_archivo_ajeno")
        if extension in VIDEO_EXT:
            video.append("/media/" + "/".join(dest))
        target = "/".join(dest).casefold()
        if target in targets:
            errors.append("manifiesto_duplicado")
        targets.add(target)
    if len(video) != 1:
        errors.append("numero_videos_invalido")
    elif not isinstance(path, str) or path != video[0]:
        errors.append("ruta_jellyfin_no_coincide")
    return errors


def evaluar_retiradas(
    snapshot: dict,
    journals: dict[int, tuple[dict, str]],
    evidences: list[dict],
) -> list[dict]:
    """Resumen por película sin título, ubicación, hash ni identidad de perfil.

    Cada fila termina en estado 'bloqueada': este método no es un autorizador.
    Si una fuente no es verificable, se añaden motivos de denegación.
    """
    if not isinstance(snapshot, dict) or not isinstance(journals, dict):
        raise ValueError("Entrada no verificable.")  # noqa: TRY004 -- contrato ValueError público
    movies = snapshot.get("peliculas")
    downloads = snapshot.get("descargas")
    profiles = snapshot.get("perfiles_activos")
    jellyfin = snapshot.get("jellyfin")
    torrents = snapshot.get("qbittorrent")
    if (
        not isinstance(movies, list) or not isinstance(downloads, list)
        or not isinstance(profiles, list) or not isinstance(jellyfin, dict)
        or not isinstance(torrents, dict) or not isinstance(evidences, list)
    ):
        raise ValueError("Fuentes de evidencia incompletas.")  # noqa: TRY004 -- contrato ValueError público
    active = {
        i for i in profiles if _bool_int(i)
    }
    jf_rows = jellyfin.get("elementos") if jellyfin.get("estado") == "ok" else []
    if not isinstance(jf_rows, list):
        jf_rows = []
    download_by_id = {
        d.get("id"): d for d in downloads if isinstance(d, dict) and _bool_int(d.get("id"))
    }
    ntfs_counts = Counter(
        p.get("download_id") for p in evidences
        if isinstance(p, dict) and _bool_int(p.get("download_id"))
    )
    download_counts = Counter(
        d.get("id") for d in downloads
        if isinstance(d, dict) and _bool_int(d.get("id"))
    )
    ntfs_by_id = {
        p.get("download_id"): p for p in evidences
        if isinstance(p, dict) and _bool_int(p.get("download_id"))
    }
    folder_counter = Counter(
        record.get("folder", "").casefold()
        for record, _ in journals.values()
        if isinstance(record, dict) and isinstance(record.get("folder"), str)
    )
    hash_counter = Counter(
        (record.get("intent") or {}).get("torrent_hash")
        for record, _ in journals.values()
        if isinstance(record, dict) and isinstance(record.get("intent"), dict)
    )
    rows: list[dict] = []
    for movie in movies:
        if not isinstance(movie, dict) or not _bool_int(movie.get("medio_id")):
            continue
        reasons: list[str] = []
        jf_id = movie.get("jellyfin_id")
        matching = [
            item for item in jf_rows
            if isinstance(item, dict) and item.get("id") == jf_id
            and item.get("tipo") == "Movie"
        ]
        if len(matching) != 1 or not isinstance(matching[0].get("path"), str):
            reasons.append("jellyfin_no_verificable")
            path = None
        else:
            path = matching[0]["path"]
        found_ids: list[int] = []
        for id_, (record, _) in journals.items():
            if not isinstance(record, dict):
                continue
            files = (record.get("intent") or {}).get("files", [])
            if not isinstance(files, list):
                continue
            for f in files:
                if not isinstance(f, dict):
                    continue
                dest = f.get("destination_relative")
                if (
                    isinstance(dest, str) and isinstance(path, str)
                    and "/media/" + dest == path
                    and PurePosixPath(dest).suffix.lower() in VIDEO_EXT
                ):
                    found_ids.append(id_)
                    break
        if len(found_ids) != 1:
            reasons.append("sin_publicacion_unica")
            if len(found_ids) > 1:
                reasons.append("publicacion_compartida_o_ambigua")
        else:
            id_ = found_ids[0]
            download = download_by_id.get(id_)
            record, journal_sha = journals[id_]
            proof = ntfs_by_id.get(id_)
            if not isinstance(download, dict) or download_counts[id_] != 1:
                reasons.append("descarga_sin_registro")
            else:
                if not isinstance(proof, dict) or ntfs_counts[id_] != 1 or (
                    proof.get("ntfs_verified") is not True
                    or proof.get("journal_sha256") != journal_sha
                    or proof.get("archivos") != len((record.get("intent") or {}).get("files", []))
                    or SHA_RE.fullmatch(journal_sha) is None
                ):
                    reasons.append("ntfs_no_verificado")
                if folder_counter[record.get("folder", "").casefold()] != 1 or hash_counter[
                    (record.get("intent") or {}).get("torrent_hash")
                ] != 1:
                    reasons.append("publicacion_compartida_o_ambigua")
                reasons.extend(_journal_match(record, download, path))
                request = download.get("solicitud")
                if (
                    not isinstance(request, dict)
                    or request.get("id") != download.get("solicitud_id")
                    or request.get("tipo_medio") != "pelicula"
                    or (request.get("jellyfin_item_id") is not None
                        and request.get("jellyfin_item_id") != jf_id)
                    or (request.get("tmdb_id") is not None
                        and movie.get("tmdb_id") is not None
                        and request.get("tmdb_id") != movie.get("tmdb_id"))
                ):
                    reasons.append("solicitud_descarga_incongruente")
                reasons.extend(_torrent_reasons(
                    download, torrents.get(str(id_), {}),
                    (record.get("intent") or {}).get("files", []),
                ))
        watched = set(movie.get("visto_perfiles", []))
        requested = set(movie.get("pendiente_perfiles", []))
        if not active or watched != active:
            reasons.append("hay_perfiles_sin_marcar_vista")
        if not requested or not requested.issubset(active) or not requested.issubset(watched):
            reasons.append("sin_peticion_valida_de_retirada")
        reasons.append("falta_autorizacion_administrador")
        rows.append({
            "medio_id": movie["medio_id"],
            "estado": "bloqueada",
            "motivos": sorted(set(reasons)),
            "puede_borrarse_ahora": False,
        })
    return sorted(rows, key=lambda item: item["medio_id"])
