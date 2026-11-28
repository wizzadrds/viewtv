"""0038: detención exclusiva por hash y ledger SQLite durable, SOLO MockTransport."""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from test_retirada_preflight_0018 import base
from worker.retirement_playback_admission_0027 import MARKER
from worker.retirement_qbit_stop_lab_0038 import (
    CustodiaQbitLab0038,
    ParadaLabRechazada,
)

from app.config import Settings
from app.qbittorrent import QBittorrentClient, QBittorrentError

HASH = "a" * 40
OTHER = "b" * 40


class FakeQbit0038:
    def __init__(self, snapshot: dict) -> None:
        self.torrent = deepcopy(snapshot["qbittorrent"]["8"]["torrent"])
        self.files = deepcopy(snapshot["qbittorrent"]["8"]["files"])
        self.other = {"hash": OTHER, "state": "uploading"}
        self.calls: list[tuple[str, str]] = []
        self.post_status = 200
        self.resumed_on_info = False
        self.info_count = 0
        self.missing = False
        self.multiple = False

    def request(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/api/v2/torrents/info":
            assert req.method == "GET"
            assert req.url.params.get("hashes") == HASH
            assert "tag" not in req.url.params
            self.info_count += 1
            if self.resumed_on_info and self.info_count > 2:
                self.torrent["state"] = "uploading"
            if self.missing:
                return httpx.Response(200, json=[])
            if self.multiple:
                return httpx.Response(
                    200, json=[deepcopy(self.torrent), deepcopy(self.other)],
                )
            return httpx.Response(200, json=[deepcopy(self.torrent)])
        if path == "/api/v2/torrents/files":
            assert req.method == "GET"
            assert req.url.params.get("hash") == HASH
            return httpx.Response(200, json=deepcopy(self.files))
        if path == "/api/v2/torrents/stop":
            assert req.method == "POST"
            data = parse_qs(req.content.decode("ascii"), strict_parsing=True)
            assert data == {"hashes": [HASH]}
            self.calls.append((req.method, path))
            if self.post_status == 200:
                self.torrent["state"] = "stoppedUP"
            return httpx.Response(self.post_status, text="ok" if self.post_status == 200 else "no")
        raise AssertionError("Ruta no permitida en qBit ficticio: " + path)


@pytest.fixture
def sandbox():
    temp = Path(tempfile.gettempdir())
    root = temp / ("viewtv-admission-0027-" + uuid.uuid4().hex)
    root.mkdir(mode=0o700)
    mark = root / "marca-0027.txt"
    mark.write_text(MARKER, encoding="ascii")
    os.chmod(mark, 0o600)
    try:
        yield root
    finally:
        shutil.rmtree(root)


def setup(sandbox, *, state="uploading", extras=False):
    snapshot, journals, _ = base()
    snapshot["qbittorrent"]["8"]["torrent"]["state"] = state
    if extras:
        snapshot["qbittorrent"]["8"]["files"].append({
            "name": "Torrent/readme.txt", "size": 488,
            "progress": 1, "priority": 0,
        })
    fake = FakeQbit0038(snapshot)
    client = QBittorrentClient(
        Settings(
            qbittorrent_base_url="http://qbit-sintetico.invalid:8080",
            qbittorrent_api_key="FICTICIA-0038",
        ),
        transport=httpx.MockTransport(fake.request),
    )
    lab = CustodiaQbitLab0038(sandbox, client)
    return lab, snapshot, journals, fake, client


def test_detiene_unicamente_hash_exacto_no_otros_torrents(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    assert lab.estado(8)["estado"] == "registrada"
    lab.ordenar_stop(8)
    assert fake.calls == [("POST", "/api/v2/torrents/stop")]
    assert fake.other["state"] == "uploading"
    assert lab.estado(8)["estado"] == "orden_enviada"
    verdict = lab.observar(8)
    assert verdict["estado"] == "parada_observada"
    assert verdict["autoriza_borrado_fisico"] is False
    assert verdict["custodia_qbit_transaccional_real"] is False
    assert verdict["torrents_productivos_modificados"] == 0


@pytest.mark.parametrize("length", [40, 64])
def test_stop_torrent_cliente_exige_un_solo_hash(length):
    client = object.__new__(QBittorrentClient)
    calls = []
    client._request = lambda *args, **kwargs: calls.append((args, kwargs))
    client.stop_torrent("a" * length)
    assert calls == [
        (("POST", "/api/v2/torrents/stop"), {"data": {"hashes": "a" * length}})
    ]


@pytest.mark.parametrize("candidate", (
    "", "all", "a" * 39, "a" * 65, "a" * 40 + "|" + "b" * 40,
    "b" * 40 + "\n", True, 32, None, ["a" * 40],
))
def test_cliente_no_puede_detener_all_listas_o_hash_invalido(candidate):
    client = object.__new__(QBittorrentClient)
    calls = []
    client._request = lambda *args, **kwargs: calls.append((args, kwargs))
    with pytest.raises(ValueError):
        client.stop_torrent(candidate)
    assert calls == []


def test_custodia_parada_no_hace_post_innecesario(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox, state="stoppedUP")
    lab.registrar(2, 8, snapshot, journals)
    lab.ordenar_stop(8)
    assert fake.calls == []
    assert lab.observar(8)["estado"] == "parada_observada"


def test_extra_se_conserva_incluso_durante_stop(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox, extras=True)
    before = deepcopy(fake.files)
    lab.registrar(2, 8, snapshot, journals)
    lab.ordenar_stop(8)
    assert lab.observar(8)["parada_observada"] is True
    assert fake.files == before
    assert fake.files[-1]["size"] == 488


def test_error_despues_del_post_no_hace_reenvio_tras_reinicio(sandbox):
    lab, snapshot, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    fake.post_status = 503
    with pytest.raises(QBittorrentError):
        lab.ordenar_stop(8)
    assert lab.estado(8)["estado"] == "orden_pendiente"
    reopened = CustodiaQbitLab0038(sandbox, client)
    with pytest.raises(ParadaLabRechazada):
        reopened.ordenar_stop(8)
    assert fake.calls == [("POST", "/api/v2/torrents/stop")]
    assert reopened.observar(8)["estado"] == "bloqueada"
    assert fake.calls == [("POST", "/api/v2/torrents/stop")]


def test_respuesta_perdida_tras_ejecucion_del_stop_puede_conciliarse(
    sandbox,
):
    lab, snapshot, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    fake.post_status = 503

    def stop_but_lose_reply(request):
        reply = fake.request(request)
        if request.url.path == "/api/v2/torrents/stop":
            fake.torrent["state"] = "stoppedUP"
        return reply

    client._transport = httpx.MockTransport(stop_but_lose_reply)
    with pytest.raises(QBittorrentError):
        lab.ordenar_stop(8)
    reopened = CustodiaQbitLab0038(sandbox, client)
    assert reopened.estado(8)["estado"] == "orden_pendiente"
    assert reopened.observar(8)["estado"] == "parada_observada"
    assert not reopened.estado(8)["autoriza_borrado_fisico"]
    with pytest.raises(ParadaLabRechazada):
        reopened.ordenar_stop(8)
    assert len(fake.calls) == 1


def test_reanudacion_por_fuera_es_bloqueo_duradero(sandbox):
    lab, snapshot, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    lab.ordenar_stop(8)
    assert lab.observar(8)["estado"] == "parada_observada"
    fake.torrent["state"] = "uploading"
    assert lab.observar(8)["estado"] == "bloqueada"
    reloaded = CustodiaQbitLab0038(sandbox, client)
    assert reloaded.estado(8)["estado"] == "bloqueada"
    with pytest.raises(ParadaLabRechazada):
        reloaded.observar(8)
    with pytest.raises(ParadaLabRechazada):
        reloaded.ordenar_stop(8)


def test_cambio_de_metadatos_extra_bloquea(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox, extras=True)
    lab.registrar(2, 8, snapshot, journals)
    lab.ordenar_stop(8)
    fake.files[-1]["size"] = 489
    assert lab.observar(8)["estado"] == "bloqueada"


def test_torrent_ajeno_en_respuesta_doble_o_ausente_bloquea(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    fake.multiple = True
    with pytest.raises(ParadaLabRechazada):
        lab.ordenar_stop(8)
    assert not fake.calls
    fake.multiple = False
    fake.missing = True
    with pytest.raises(ParadaLabRechazada):
        lab.ordenar_stop(8)
    assert not fake.calls


@pytest.mark.parametrize("mutation", (
    lambda s: s["descargas"][0].update(hash="b" * 40),
    lambda s: s["peliculas"][0].update(medio_id=3),
    lambda s: s["descargas"][0]["solicitud"].update(tmdb_id=999),
    lambda s: s["descargas"][0].update(verificada=False),
    lambda s: s["qbittorrent"]["8"]["torrent"].update(tags="otro"),
    lambda s: s["qbittorrent"]["8"]["torrent"].update(save_path="C:\\Otro"),
    lambda s: s["qbittorrent"]["8"]["files"][0].update(progress=0.5),
    lambda s: s["qbittorrent"]["8"]["files"][0].update(size=3),
))
def test_no_se_crea_orden_sin_identidad_fuerte(sandbox, mutation):
    lab, snapshot, journals, fake, _client = setup(sandbox)
    mutation(snapshot)
    with pytest.raises((ParadaLabRechazada, ValueError)):
        lab.registrar(2, 8, snapshot, journals)
    assert not fake.calls


@pytest.mark.parametrize("value", (0, -1, 9999, True, "8", None))
def test_descarga_no_registrada_o_de_identidad_invalida(sandbox, value):
    lab, _snapshot, _journals, _fake, _client = setup(sandbox)
    with pytest.raises(ParadaLabRechazada):
        lab.ordenar_stop(value)


def test_no_acepta_cliente_con_transporte_real(sandbox):
    with pytest.raises(ParadaLabRechazada):
        CustodiaQbitLab0038(
            sandbox,
            QBittorrentClient(
                Settings(
                    qbittorrent_base_url="http://localhost:8080",
                    qbittorrent_api_key="no-real",
                ),
            ),
        )


def test_sandbox_privado_impide_ledger_ajeno(sandbox):
    lab, snapshot, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    os.chmod(lab.db, 0o644)
    with pytest.raises(ParadaLabRechazada):
        CustodiaQbitLab0038(sandbox, client)
    assert fake.calls == []


def test_reanudacion_entre_dos_get_bloquea(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    lab.ordenar_stop(8)
    fake.resumed_on_info = True
    answer = lab.observar(8)
    assert answer["estado"] == "bloqueada"
    assert not answer["autoriza_borrado_fisico"]
    assert len(fake.calls) == 1


def test_dos_operadores_concurrentes_solo_emiten_un_stop(sandbox):
    from concurrent.futures import ThreadPoolExecutor

    lab, snapshot, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    second = CustodiaQbitLab0038(sandbox, client)

    def attempt(lab_client):
        try:
            lab_client.ordenar_stop(8)
            return "ok"
        except ParadaLabRechazada:
            return "bloqueada"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [lab, second]))
    assert sorted(results) == ["bloqueada", "ok"]
    assert fake.calls == [("POST", "/api/v2/torrents/stop")]
    assert lab.estado(8)["estado"] == "orden_enviada"


def test_dos_registros_o_dos_descargas_no_aparecen_por_error(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    with pytest.raises(ParadaLabRechazada):
        lab.registrar(2, 8, snapshot, journals)
    assert fake.calls == []


def test_reanudacion_antes_de_orden_no_auto_pausa_torrent_incompleto(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    fake.torrent["progress"] = 0.2
    with pytest.raises(ParadaLabRechazada):
        lab.ordenar_stop(8)
    assert fake.calls == []
    assert lab.estado(8)["estado"] == "registrada"


def test_file_priority_cambio_impide_aceptar_parada(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox, extras=True)
    lab.registrar(2, 8, snapshot, journals)
    lab.ordenar_stop(8)
    fake.files[-1]["priority"] = 1
    assert lab.observar(8)["estado"] == "bloqueada"


def test_diario_con_hash_ajeno_no_prepara_stop(sandbox):
    lab, snapshot, journals, fake, _client = setup(sandbox)
    journals[8][0]["intent"]["torrent_hash"] = OTHER
    with pytest.raises(ParadaLabRechazada):
        lab.registrar(2, 8, snapshot, journals)
    assert fake.calls == []


def test_caida_real_proceso_despues_post_no_reenvia_stop(sandbox):
    """La SQLite conserva la orden antes de que os._exit mate al emisor."""
    import subprocess
    import sys

    lab, snapshot, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snapshot, journals)
    child = """
import os
import sys
from pathlib import Path

import httpx
from app.config import Settings
from app.qbittorrent import QBittorrentClient
from worker.retirement_qbit_stop_lab_0038 import CustodiaQbitLab0038
from worker.retirement_preflight_0018 import TORRENT_ROOT

root = Path(sys.argv[1])
file_path = root / 'orden_mock_enviada.txt'
hash_ = 'a' * 40

def handler(req):
    if req.url.path == '/api/v2/torrents/info':
        return httpx.Response(200, json=[{
            'hash': hash_, 'tags': 'viewtv-descarga-8',
            'save_path': str(TORRENT_ROOT), 'state': 'uploading',
            'progress': 1,
        }])
    if req.url.path == '/api/v2/torrents/files':
        return httpx.Response(200, json=[{
            'name': 'Torrent/Film.mkv', 'size': 1024,
            'progress': 1, 'priority': 1,
        }])
    if req.url.path == '/api/v2/torrents/stop':
        fd = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, b'UNA_UNICA_ORDEN_MOCK')
            os.fsync(fd)
        finally:
            os.close(fd)
        os._exit(77)
    raise RuntimeError('Operacion qBit ajena al experimento')

client = QBittorrentClient(
    Settings(
        qbittorrent_base_url='http://sin-red.invalid:8080',
        qbittorrent_api_key='simulada',
    ),
    transport=httpx.MockTransport(handler),
)
CustodiaQbitLab0038(root, client).ordenar_stop(8)
"""
    proc = subprocess.run(
        [sys.executable, "-c", child, str(sandbox)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    assert proc.returncode == 77, proc.stderr
    assert (sandbox / "orden_mock_enviada.txt").read_bytes() == (
        b"UNA_UNICA_ORDEN_MOCK"
    )
    reopened = CustodiaQbitLab0038(sandbox, client)
    assert reopened.estado(8)["estado"] == "orden_pendiente"
    with pytest.raises(ParadaLabRechazada):
        reopened.ordenar_stop(8)
    assert fake.calls == []
    # La orden de prueba salió justo antes del crash. Una lectura nueva
    # puede observar parado, pero NUNCA otorgar permiso de eliminación.
    fake.torrent["state"] = "stoppedUP"
    assert reopened.observar(8)["estado"] == "parada_observada"
    assert not reopened.estado(8)["autoriza_borrado_fisico"]
