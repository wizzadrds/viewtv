"""Bounded, marked loopback-only qBittorrent HTTP fixture (no real torrents).

Test server lifecycle CLI for VIEWTV 0013:
  --action serve|status|set-mode|stop --guid <32-lower-hex>
  serve also takes --download-id and --torrent-hash.
All temporary files must be owned by the fixture under /tmp with a GUID.
The only remote address is 127.0.0.1, and only GET is implemented.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread, Timer
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

_GUID = re.compile(r"[a-f0-9]{32}\Z")
_HASH = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")
_VALID_MODES = {
    "valid",
    "foreign_tag",
    "incomplete",
    "wrong_path",
    "wrong_hash",
    "duplicate_files",
    "bad_marker",
}
_MARKER = "VIEWTV_FAKE_QBIT_HTTP_ONLY_V1\n"


def _paths(guid: str) -> tuple[Path, Path, Path, Path]:
    if _GUID.fullmatch(guid) is None:
        raise ValueError("Sandbox GUID invalid")
    root = Path("/tmp") / f"viewtv-qbit-http-{guid}"
    return root, root / ".viewtv-http-only", root / "mode.txt", root / "ready.json"


def _assert_own_fixture(guid: str) -> tuple[Path, Path, Path, Path]:
    root, marker, mode, ready = _paths(guid)
    if (
        not root.is_dir()
        or root.is_symlink()
        or not marker.is_file()
        or marker.is_symlink()
        or marker.read_text(encoding="utf-8") != _MARKER
    ):
        raise ValueError("No matching owned HTTP fixture")
    return root, marker, mode, ready


def _read_ready(guid: str) -> str:
    _, _, _, ready = _assert_own_fixture(guid)
    if not ready.is_file() or ready.is_symlink():
        raise ValueError("Fixture is not ready")
    item = json.loads(ready.read_text(encoding="utf-8"))
    url = item.get("base_url")
    if (
        not isinstance(url, str)
        or re.fullmatch(r"http://127\.0\.0\.1:([0-9]{5})", url) is None
        or not 49152 <= int(url.rsplit(":", 1)[1]) <= 65535
    ):
        raise ValueError("Ready URL is not loopback sandbox")
    return url


def _fixture_handler(guid: str, download_id: int, torrent_hash: str, mode_file: Path):
    class FixtureHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            uri = urlsplit(self.path)
            query = parse_qs(uri.query, keep_blank_values=True)
            if uri.path == "/viewtv-test/stop":
                if query != {"guid": [guid]}:
                    self.send_error(404)
                    return
                self._json({"stopping": True})
                Thread(target=self.server.shutdown, daemon=True).start()
                return
            if uri.path == "/viewtv-test/marker":
                if query != {"guid": [guid]}:
                    self.send_error(404)
                    return
                data = {
                    "version": 1,
                    "sandbox": f"viewtv-win-sandbox-{guid}",
                    "test_only": True,
                }
                if mode_file.read_text(encoding="utf-8") == "bad_marker":
                    data["test_only"] = False
                self._json(data)
                return
            if uri.path == "/api/v2/torrents/info":
                if query != {"hashes": [torrent_hash]}:
                    self.send_error(400)
                    return
                mode = mode_file.read_text(encoding="utf-8")
                item = {
                    "hash": "b" * 40 if mode == "wrong_hash" else torrent_hash,
                    "tags": (
                        f"viewtv-descarga-{download_id + 1}"
                        if mode == "foreign_tag"
                        else f"viewtv-descarga-{download_id}"
                    ),
                    "state": "downloading" if mode == "incomplete" else "stoppedUP",
                    "save_path": (
                        r"C:\VIEWTV\media"
                        if mode == "wrong_path"
                        else rf"C:\Users\Public\viewtv-win-sandbox-{guid}\stage"
                    ),
                    "progress": 0.5 if mode == "incomplete" else 1.0,
                    "total_size": 8,
                }
                self._json([item])
                return
            if uri.path == "/api/v2/torrents/files":
                if query != {"hash": [torrent_hash]}:
                    self.send_error(400)
                    return
                files = [
                    {"name": "video.mkv", "size": 5, "progress": 1.0, "priority": 1},
                    {"name": "video.srt", "size": 3, "progress": 1.0, "priority": 1},
                ]
                if mode_file.read_text(encoding="utf-8") == "duplicate_files":
                    files[1]["name"] = "VIDEO.MKV"
                self._json(files)
                return
            self.send_error(404)

        def _json(self, obj: object) -> None:
            data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args: object) -> None:
            return

    return FixtureHandler


def _serve(guid: str, download_id: int, torrent_hash: str) -> None:
    if download_id <= 0 or _HASH.fullmatch(torrent_hash) is None:
        raise ValueError("Fixture identity invalid")
    root, marker, mode, ready = _paths(guid)
    # Never reuse or delete an existing directory, even if its GUID matches.
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    server = None
    watchdog = None
    try:
        marker.write_text(_MARKER, encoding="utf-8")
        mode.write_text("valid", encoding="utf-8")
        handler = _fixture_handler(guid, download_id, torrent_hash, mode)
        for _ in range(90):
            port = 49152 + secrets.randbelow(65536 - 49152)
            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), handler)
                break
            except OSError:
                continue
        if server is None:
            raise OSError("No free high-port loopback listener")
        ready.write_text(
            json.dumps({"base_url": f"http://127.0.0.1:{port}"}),
            encoding="utf-8",
        )
        # Automatic lifetime bound even if the PowerShell client crashes.
        watchdog = Timer(90, server.shutdown)
        watchdog.daemon = True
        watchdog.start()
        server.serve_forever(poll_interval=0.05)
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if server is not None:
            server.server_close()
        if (
            root.is_dir()
            and not root.is_symlink()
            and marker.is_file()
            and marker.read_text(encoding="utf-8") == _MARKER
            and {item.name for item in root.iterdir()}
            <= {marker.name, mode.name, ready.name}
            and all(not item.is_symlink() for item in root.iterdir())
        ):
            shutil.rmtree(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action", choices=("serve", "status", "set-mode", "stop"), required=True
    )
    parser.add_argument("--guid", required=True)
    parser.add_argument("--download-id", type=int)
    parser.add_argument("--torrent-hash")
    parser.add_argument("--mode", choices=sorted(_VALID_MODES))
    a = parser.parse_args()
    _paths(a.guid)
    if a.action == "serve":
        if a.download_id is None or a.torrent_hash is None:
            parser.error("serve needs download-id and torrent-hash")
        _serve(a.guid, a.download_id, a.torrent_hash)
    elif a.action == "status":
        print(json.dumps({"base_url": _read_ready(a.guid)}, separators=(",", ":")))
    elif a.action == "set-mode":
        if a.mode is None:
            parser.error("set-mode needs --mode")
        _, _, mode, _ = _assert_own_fixture(a.guid)
        if mode.is_symlink() or not mode.is_file():
            raise ValueError("Mode file is not safe")
        mode.write_text(a.mode, encoding="utf-8")
        print(json.dumps({"mode": a.mode}, separators=(",", ":")))
    else:
        url = _read_ready(a.guid)
        with urlopen(f"{url}/viewtv-test/stop?guid={a.guid}", timeout=3) as response:
            if response.status != 200:
                raise ValueError("Stop was not acknowledged")
        print(json.dumps({"stop_requested": True}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
