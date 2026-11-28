"""GET-only torrent identity probe for a marked loopback qBittorrent test fixture.

This is NOT the real qBittorrent API and NEVER uses production settings,
credentials, torrents, files, containers or a publication capability.
The fixture handshake prevents accidentally treating a normal qBittorrent
instance as a valid test source. Identity is only true at query time.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import PureWindowsPath

import httpx

from worker.completed_files import COMPLETE_STATES

_GUID = re.compile(r"[a-f0-9]{32}\Z")
_HASH = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")
_BASE = re.compile(r"http://127\.0\.0\.1:([0-9]{1,5})\Z")
_MAX_BYTES = 32 * 1024 * 1024
_MAX_RESPONSE = 16 * 1024
_VIDEO = {".mkv", ".mp4", ".avi", ".webm"}
_SUBTITLES = {".srt", ".ass", ".ssa", ".vtt"}
_MARKER_PATH = "/viewtv-test/marker"


@dataclass(frozen=True)
class TorrentProbeDecision:
    allowed: bool
    code: str


class _NotTrustedFixture(ValueError):
    pass


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    if len(pairs) != len({key for key, _ in pairs}):
        raise _NotTrustedFixture("Duplicated JSON key")
    return dict(pairs)


def _no_constant(_: str) -> None:
    raise _NotTrustedFixture("Non-finite JSON constant")


def _read_get(client: httpx.Client, path: str, *, params: dict[str, str]) -> object:
    # Only GET; response size is bounded even when Content-Length is missing.
    with client.stream("GET", path, params=params) as reply:
        if reply.status_code != 200:
            raise _NotTrustedFixture("Unexpected status/redirect")
        declared = reply.headers.get("content-length")
        if declared is not None and (
            not declared.isascii()
            or not declared.isdigit()
            or int(declared) > _MAX_RESPONSE
        ):
            raise _NotTrustedFixture("Invalid Content-Length")
        body = bytearray()
        for chunk in reply.iter_bytes():
            if len(body) + len(chunk) > _MAX_RESPONSE:
                raise _NotTrustedFixture("Overlong response")
            body.extend(chunk)
    return json.loads(
        body.decode("utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_no_constant,
    )


def _safe_fake_file(name: object) -> str:
    if not isinstance(name, str) or not name or len(name) > 230:
        raise _NotTrustedFixture("Bad file name")
    # A fake torrent must not include paths escaping its synthetic folder.
    parts = name.replace("\\", "/").split("/")
    if any(
        not part
        or part in (".", "..")
        or part.endswith((" ", "."))
        or ":" in part
        or any(ord(c) < 32 for c in part)
        or re.fullmatch(
            r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?",
            part,
        )
        for part in parts
    ):
        raise _NotTrustedFixture("Unsafe path segment")
    return "/".join(parts).casefold()


def check_sandbox_torrent_http(
    base_url: str,
    fixture_guid: str,
    download_id: int,
    expected_hash: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> TorrentProbeDecision:
    """Probe a uniquely marked fake qBittorrent HTTP server, fail-closed.

    The only accepted host is 127.0.0.1, with an ephemeral port.
    An authenticated owner tag, complete state and matching synthetic
    save path are mandatory. This does not verify NTFS bytes or a lease.
    """
    match = _BASE.fullmatch(base_url) if isinstance(base_url, str) else None
    if (
        match is None
        or not 49152 <= int(match.group(1)) <= 65535
        or not isinstance(fixture_guid, str)
        or _GUID.fullmatch(fixture_guid) is None
        or type(download_id) is not int
        or download_id <= 0
        or not isinstance(expected_hash, str)
        or _HASH.fullmatch(expected_hash) is None
    ):
        return TorrentProbeDecision(False, "identidad_invalida")

    expected_tag = f"viewtv-descarga-{download_id}"
    expected_path = rf"C:\Users\Public\viewtv-win-sandbox-{fixture_guid}\stage"
    try:
        with httpx.Client(
            base_url=base_url,
            headers={"Authorization": "Bearer VIEWTV_SANDBOX_TEST_ONLY"},
            timeout=1.5,
            transport=transport,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            marker = _read_get(client, _MARKER_PATH, params={"guid": fixture_guid})
            if (
                not isinstance(marker, dict)
                or len(marker) != 3
                or set(marker) != {"version", "sandbox", "test_only"}
                or type(marker["version"]) is not int
                or marker["version"] != 1
                or marker["sandbox"] != f"viewtv-win-sandbox-{fixture_guid}"
                or type(marker["test_only"]) is not bool
                or marker["test_only"] is not True
            ):
                raise _NotTrustedFixture("Missing test marker")

            info = _read_get(
                client,
                "/api/v2/torrents/info",
                params={"hashes": expected_hash},
            )
            if not isinstance(info, list) or len(info) != 1:
                raise _NotTrustedFixture("Missing/ambiguous torrent")
            torrent = info[0]
            if not isinstance(torrent, dict):
                raise _NotTrustedFixture("Unexpected torrent object")
            labels = torrent.get("tags")
            if not isinstance(labels, str):
                raise _NotTrustedFixture("Bad tags")
            tag_set = [tag.strip() for tag in labels.split(",")]
            if (
                expected_tag not in tag_set
                or len(tag_set) != len(set(tag_set))
                or any(
                    tag.startswith("viewtv-descarga-") and tag != expected_tag
                    for tag in tag_set
                )
            ):
                raise _NotTrustedFixture("Foreign/ambiguous owner")
            total = torrent.get("total_size")
            progress = torrent.get("progress")
            if (
                torrent.get("hash") != expected_hash
                or torrent.get("state") not in COMPLETE_STATES
                or type(total) is not int
                or not 0 < total <= _MAX_BYTES
                or type(progress) not in (float, int)
                or not math.isfinite(progress)
                or progress != 1
                or not isinstance(torrent.get("save_path"), str)
                or str(PureWindowsPath(torrent["save_path"])).casefold()
                != expected_path.casefold()
            ):
                raise _NotTrustedFixture("Untrusted torrent state")

            files = _read_get(
                client,
                "/api/v2/torrents/files",
                params={"hash": expected_hash},
            )
            if not isinstance(files, list) or not 1 <= len(files) <= 20:
                raise _NotTrustedFixture("Invalid file list")
            seen: set[str] = set()
            file_total = 0
            videos = 0
            for item in files:
                if not isinstance(item, dict):
                    raise _NotTrustedFixture("File item not an object")
                name = _safe_fake_file(item.get("name"))
                if name in seen:
                    raise _NotTrustedFixture("Case-colliding files")
                seen.add(name)
                ext = PureWindowsPath(name).suffix
                if ext in _VIDEO:
                    videos += 1
                elif ext not in _SUBTITLES:
                    raise _NotTrustedFixture("Unexpected extension")
                size = item.get("size")
                percent = item.get("progress")
                priority = item.get("priority")
                if (
                    type(size) is not int
                    or not 0 < size <= _MAX_BYTES
                    or type(percent) not in (int, float)
                    or not math.isfinite(percent)
                    or percent != 1
                    or type(priority) is not int
                    or priority <= 0
                ):
                    raise _NotTrustedFixture("Unfinished/unselected file")
                file_total += size
            if videos != 1 or file_total != total:
                raise _NotTrustedFixture("Ambiguous/incomplete content")
    except (httpx.HTTPError, ValueError, UnicodeError, OverflowError):
        return TorrentProbeDecision(False, "torrent_ficticio_no_verificable")
    return TorrentProbeDecision(True, "torrent_ficticio_vigente_en_consulta")
