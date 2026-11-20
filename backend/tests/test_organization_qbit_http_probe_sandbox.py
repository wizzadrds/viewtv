"""Fictional qBittorrent GET HTTP responses; never real qBittorrent or files."""

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit

import httpx
import pytest
from worker.organization_qbit_http_probe_sandbox import (
    check_sandbox_torrent_http,
)

GUID = "e" * 32
BASE = "http://127.0.0.1:54321"
HASH = "a" * 40
DID = 17
PATH = rf"C:\Users\Public\viewtv-win-sandbox-{GUID}\stage"


def sample():
    return {
        "marker": {
            "version": 1,
            "sandbox": f"viewtv-win-sandbox-{GUID}",
            "test_only": True,
        },
        "info": [
            {
                "hash": HASH,
                "tags": "otro,viewtv-descarga-17",
                "state": "stoppedUP",
                "save_path": PATH,
                "progress": 1.0,
                "total_size": 8,
            }
        ],
        "files": [
            {"name": "video.mkv", "size": 5, "progress": 1.0, "priority": 1},
            {"name": "video.srt", "size": 3, "progress": 1.0, "priority": 1},
        ],
    }


def fixture_response(data, *, events=None, status=200):
    if events is None:
        events = []

    def handler(request: httpx.Request):
        events.append((request.method, request.url.path, dict(request.url.params)))
        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer VIEWTV_SANDBOX_TEST_ONLY"
        assert request.url.host == "127.0.0.1"
        if request.url.path == "/viewtv-test/marker":
            assert request.url.params["guid"] == GUID
            return httpx.Response(status, json=data["marker"])
        if request.url.path == "/api/v2/torrents/info":
            assert request.url.params["hashes"] == HASH
            return httpx.Response(status, json=data["info"])
        if request.url.path == "/api/v2/torrents/files":
            assert request.url.params["hash"] == HASH
            return httpx.Response(status, json=data["files"])
        raise AssertionError(f"Unexpected fixture route: {request.url.path}")

    return httpx.MockTransport(handler)


def probe(data, *, events=None):
    return check_sandbox_torrent_http(
        BASE, GUID, DID, HASH, transport=fixture_response(data, events=events)
    )


def test_only_get_and_three_expected_routes():
    events = []
    result = probe(sample(), events=events)
    assert result.allowed
    assert result.code == "torrent_ficticio_vigente_en_consulta"
    assert events == [
        ("GET", "/viewtv-test/marker", {"guid": GUID}),
        ("GET", "/api/v2/torrents/info", {"hashes": HASH}),
        ("GET", "/api/v2/torrents/files", {"hash": HASH}),
    ]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:54321",
        "http://127.0.0.2:54321",
        "https://127.0.0.1:54321",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:49151",
        "http://127.0.0.1:65536",
        "http://127.0.0.1:54321/api/v2/torrents/info",
        "http://user@127.0.0.1:54321",
        "http://127.0.0.1:54321?unexpected=true",
        "http://127.0.0.1:54321/",
    ],
)
def test_rejects_any_nonfixture_host_or_url_without_http(url):
    events = []
    result = check_sandbox_torrent_http(
        url, GUID, DID, HASH, transport=fixture_response(sample(), events=events)
    )
    assert not result.allowed
    assert result.code == "identidad_invalida"
    assert events == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fixture_guid": "ABC" * 10 + "AB"},
        {"fixture_guid": "e" * 31},
        {"download_id": True},
        {"download_id": 0},
        {"download_id": "17"},
        {"expected_hash": "x" * 40},
        {"expected_hash": "A" * 40},
        {"expected_hash": "a" * 41},
    ],
)
def test_invalid_inputs_reject_before_http(kwargs):
    args = dict(
        base_url=BASE,
        fixture_guid=GUID,
        download_id=DID,
        expected_hash=HASH,
    )
    args.update(kwargs)
    events = []
    result = check_sandbox_torrent_http(**args, transport=fixture_response(sample(), events=events))
    assert not result.allowed
    assert result.code == "identidad_invalida"
    assert events == []


@pytest.mark.parametrize(
    "marker",
    [
        {},
        {"version": 1, "sandbox": "viewtv-win-sandbox-" + "f" * 32, "test_only": True},
        {"version": 1, "sandbox": f"viewtv-win-sandbox-{GUID}", "test_only": "true"},
        {"version": 1, "sandbox": f"viewtv-win-sandbox-{GUID}", "test_only": 1},
        {"version": 1.0, "sandbox": f"viewtv-win-sandbox-{GUID}", "test_only": True},
        {"version": 1, "sandbox": f"viewtv-win-sandbox-{GUID}", "test_only": True, "extra": 1},
        [],
    ],
)
def test_missing_or_spoofed_fixture_marker_denies_without_torrent_reads(marker):
    data = sample()
    data["marker"] = marker
    events = []
    result = probe(data, events=events)
    assert not result.allowed
    assert len(events) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"hash": "b" * 40},
        {"tags": "viewtv-descarga-18"},
        {"tags": "viewtv-descarga-17,viewtv-descarga-18"},
        {"tags": "viewtv-descarga-17,viewtv-descarga-17"},
        {"tags": ""},
        {"state": "downloading"},
        {"state": "checkingUP"},
        {"progress": 0.99},
        {"progress": True},
        {"save_path": r"C:\VIEWTV\media\descargas_temporales"},
        {"save_path": rf"C:\Users\Public\viewtv-win-sandbox-{GUID}\..\otra"},
        {"save_path": None},
        {"total_size": 7},
        {"total_size": 0},
        {"total_size": True},
        {"total_size": 40 * 1024 * 1024},
    ],
)
def test_wrong_torrent_identity_or_state_is_denied_before_files(change):
    data = sample()
    data["info"][0].update(change)
    events = []
    result = probe(data, events=events)
    assert not result.allowed
    # A size mismatch needs the final GET /files to compare lengths.
    assert len(events) == (3 if change == {"total_size": 7} else 2)


@pytest.mark.parametrize(
    "infos",
    [
        [],
        [{}, {}],
        "not-a-list",
        [None],
        [1],
    ],
)
def test_ambiguous_or_missing_torrent_is_denied(infos):
    data = sample()
    data["info"] = infos
    events = []
    assert not probe(data, events=events).allowed
    assert len(events) == 2


@pytest.mark.parametrize(
    "files",
    [
        [],
        [{"name": "../video.mkv", "size": 8, "progress": 1, "priority": 1}],
        [{"name": r"C:\real\video.mkv", "size": 8, "progress": 1, "priority": 1}],
        [{"name": "video.mkv", "size": 8, "progress": 0.9, "priority": 1}],
        [{"name": "video.mkv", "size": 8, "progress": True, "priority": 1}],
        [{"name": "video.mkv", "size": 8, "progress": 1, "priority": 0}],
        [{"name": "video.mkv", "size": 7, "progress": 1, "priority": 1}],
        [{"name": "video.exe", "size": 8, "progress": 1, "priority": 1}],
        [{"name": "CON.mkv", "size": 8, "progress": 1, "priority": 1}],
        [
            {"name": "video.mkv", "size": 5, "progress": 1, "priority": 1},
            {"name": "VIDEO.MKV", "size": 3, "progress": 1, "priority": 1},
        ],
        [{"name": "video.srt", "size": 8, "progress": 1, "priority": 1}],
        [{"name": "video.mkv", "size": True, "progress": 1, "priority": 1}],
        None,
    ],
)
def test_malicious_or_incomplete_file_list_denied(files):
    data = sample()
    data["files"] = files
    events = []
    assert not probe(data, events=events).allowed
    assert len(events) == 3


@pytest.mark.parametrize("code", [301, 302, 401, 403, 500])
def test_redirect_or_error_never_authorizes(code):
    events = []
    transport = fixture_response(sample(), events=events, status=code)
    decision = check_sandbox_torrent_http(BASE, GUID, DID, HASH, transport=transport)
    assert not decision.allowed
    assert len(events) == 1


def test_truncated_and_duplicated_json_fail_closed():
    calls = []

    def bad_response(req: httpx.Request):
        calls.append(req.url.path)
        return httpx.Response(
            200,
            content=(
                '{"version":1,"sandbox":"viewtv-win-sandbox-'
                + GUID
                + '","test_only":true,"version":1}'
            ).encode(),
        )

    decision = check_sandbox_torrent_http(
        BASE, GUID, DID, HASH, transport=httpx.MockTransport(bad_response)
    )
    assert not decision.allowed
    assert calls == ["/viewtv-test/marker"]


def test_overlong_response_rejected_before_requesting_torrents():
    calls = []

    def oversized(req: httpx.Request):
        calls.append(req.url.path)
        return httpx.Response(200, content=b"x" * 17000)

    decision = check_sandbox_torrent_http(
        BASE, GUID, DID, HASH, transport=httpx.MockTransport(oversized)
    )
    assert not decision.allowed
    assert calls == ["/viewtv-test/marker"]


def test_connection_loss_denied_without_retry():
    calls = []

    def offline(req: httpx.Request):
        calls.append(req.url.path)
        raise httpx.ConnectTimeout("fake fixture timeout")

    decision = check_sandbox_torrent_http(
        BASE, GUID, DID, HASH, transport=httpx.MockTransport(offline)
    )
    assert not decision.allowed
    assert calls == ["/viewtv-test/marker"]


def test_real_loopback_server_get_only():
    """Run a genuine local HTTP GET exchange, never a real torrent client."""
    data = sample()
    requests_seen = []

    class FakeQbitHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlsplit(self.path).path
            requests_seen.append(("GET", route))
            records = {
                "/viewtv-test/marker": data["marker"],
                "/api/v2/torrents/info": data["info"],
                "/api/v2/torrents/files": data["files"],
            }
            if route not in records:
                self.send_error(404)
                return
            body = json.dumps(records[route]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            requests_seen.append(("POST", self.path))
            self.send_error(405)

        def log_message(self, *args):
            pass

    # Linux may repeatedly reuse the same low ephemeral port when we bind
    # port zero. Try randomly chosen HIGH ports; never attach to a process
    # that already owns a port.
    server = None
    for _ in range(40):
        test_port = 49152 + secrets.randbelow(65536 - 49152)
        try:
            server = ThreadingHTTPServer(("127.0.0.1", test_port), FakeQbitHandler)
            break
        except OSError:
            continue
    if server is None:
        pytest.skip("No free high-port loopback test listener")

    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        decision = check_sandbox_torrent_http(
            f"http://127.0.0.1:{server.server_port}", GUID, DID, HASH
        )
        assert decision.allowed
        assert requests_seen == [
            ("GET", "/viewtv-test/marker"),
            ("GET", "/api/v2/torrents/info"),
            ("GET", "/api/v2/torrents/files"),
        ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert not thread.is_alive()


def test_sha256_torrent_hash_accepted():
    fixture = sample()
    torrent_hash = "c" * 64
    fixture["info"][0]["hash"] = torrent_hash

    def handler(req: httpx.Request):
        if req.url.path == "/viewtv-test/marker":
            return httpx.Response(200, json=fixture["marker"])
        if req.url.path == "/api/v2/torrents/info":
            assert req.url.params["hashes"] == torrent_hash
            return httpx.Response(200, json=fixture["info"])
        if req.url.path == "/api/v2/torrents/files":
            assert req.url.params["hash"] == torrent_hash
            return httpx.Response(200, json=fixture["files"])
        raise AssertionError("Unexpected URL")

    assert check_sandbox_torrent_http(
        BASE, GUID, DID, torrent_hash, transport=httpx.MockTransport(handler)
    ).allowed
