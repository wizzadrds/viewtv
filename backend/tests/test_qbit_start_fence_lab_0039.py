"""0039: fence de starts VIEWTV con SQLite privada; nunca qBit real."""
from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs

import httpx
import pytest
import worker.download_starter as starter
from test_qbit_stop_lab_0038 import setup
from test_release_one_torrent_start import saved
from worker.download_processor import STAGING_PATH
from worker.retirement_qbit_start_fence_lab_0039 import InicioCustodiadoLab0039
from worker.retirement_qbit_stop_lab_0038 import (
    CustodiaQbitLab0038,
    ParadaLabRechazada,
)

pytest_plugins = (
    "test_qbit_stop_lab_0038",
    "test_release_one_torrent_start",
)


@pytest.fixture(name="start_lab")
def _starting_lab(request):
    return request.getfixturevalue("lab")


HASH_A = "a" * 40
HASH_B = "b" * 40


def test_custodia_registrada_cierra_start_antes_de_enviar_stop(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    gate = InicioCustodiadoLab0039(lab)
    lab.registrar(2, 8, snap, journals)
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(HASH_A)
    assert lab.estado(8)["estado"] == "registrada"
    assert fake.calls == []
    assert gate.estado_custodia(8)["autoriza_borrado_fisico"] is False


@pytest.mark.parametrize("state", (
    "registrada", "orden_pendiente", "orden_enviada",
    "parada_observada", "bloqueada",
))
def test_no_reinicia_hash_custodiado_en_ningun_estado(sandbox, state):
    lab, snap, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snap, journals)
    # Laboratorio autónomo: reproducir estado durable, no qBit real.
    with lab._tx() as conn:
        conn.execute("UPDATE custodia SET estado=? WHERE descarga=8", (state,))
    gate = InicioCustodiadoLab0039(CustodiaQbitLab0038(sandbox, client))
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(HASH_A)
    assert fake.calls == []


def test_fence_se_conserva_tras_reabrir_base_y_no_tiene_ttl(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snap, journals)
    for _ in range(3):
        new = InicioCustodiadoLab0039(CustodiaQbitLab0038(sandbox, client))
        with pytest.raises(ParadaLabRechazada):
            new.start_torrent(HASH_A)
    assert fake.calls == []


@pytest.mark.parametrize("hash_", (
    "", "all", "a" * 39, "a" * 41, "a" * 65, "X" * 40,
    "a" * 40 + "|" + "b" * 40, None, True, ["a" * 40],
))
def test_rechaza_cadenas_peligrosas_antes_de_acceder_a_http(sandbox, hash_):
    lab, _snap, _journals, fake, _client = setup(sandbox)
    gate = InicioCustodiadoLab0039(lab)
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(hash_)
    assert fake.calls == []


def test_fail_closed_si_transport_se_sustituye_por_uno_real(sandbox):
    lab, snap, journals, _fake, client = setup(sandbox)
    lab.registrar(2, 8, snap, journals)
    gate = InicioCustodiadoLab0039(lab)
    client._transport = None
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(HASH_B)
    with pytest.raises(ParadaLabRechazada):
        gate.torrents_info(tag="viewtv-descarga-8")
    with pytest.raises(ParadaLabRechazada):
        InicioCustodiadoLab0039(lab)


def test_fail_closed_si_ledger_no_privado(sandbox):
    lab, _snap, _journals, _fake, client = setup(sandbox)
    gate = InicioCustodiadoLab0039(lab)
    lab.db.chmod(0o644)
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(HASH_B)
    with pytest.raises(ParadaLabRechazada):
        CustodiaQbitLab0038(sandbox, client)


def test_inicio_fuera_del_hash_objetivo_no_se_bloquea(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snap, journals)
    starts = []

    def handler(req):
        if req.url.path == "/api/v2/torrents/start":
            form = parse_qs(req.content.decode("ascii"), strict_parsing=True)
            assert form == {"hashes": [HASH_B]}
            starts.append(HASH_B)
            return httpx.Response(200, text="Ok.")
        return fake.request(req)

    client._transport = httpx.MockTransport(handler)
    gate = InicioCustodiadoLab0039(lab)
    gate.start_torrent(HASH_B)
    assert starts == [HASH_B]
    assert lab.estado(8)["estado"] == "registrada"
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(HASH_A)
    assert starts == [HASH_B]


def test_registrar_custodia_no_acepta_start_ya_emitido(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    entered = threading.Event()
    resume = threading.Event()
    registered = threading.Event()
    calls = []

    def handler(req):
        if req.url.path == "/api/v2/torrents/start":
            assert parse_qs(req.content.decode("ascii")) == {
                "hashes": [HASH_A],
            }
            calls.append("START")
            entered.set()
            assert resume.wait(2)
            return httpx.Response(200, text="Ok.")
        return fake.request(req)

    client._transport = httpx.MockTransport(handler)
    gate = InicioCustodiadoLab0039(lab)

    def register():
        try:
            lab.registrar(2, 8, snap, journals)
            registered.set()
        except ParadaLabRechazada:
            return "bloqueada"
        return "registrada"

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_start = pool.submit(gate.start_torrent, HASH_A)
        assert entered.wait(2)
        future_register = pool.submit(register)
        try:
            assert not registered.wait(0.15)
        finally:
            resume.set()
        future_start.result(timeout=3)
        assert future_register.result(timeout=3) == "bloqueada"

    assert not registered.is_set()
    assert calls == ["START"]
    assert gate.estado_intencion(HASH_A)["estado"] == "confirmada"
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(HASH_A)
    assert calls == ["START"]


def test_un_start_pendiente_luego_de_registrar_se_rechaza(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    gate = InicioCustodiadoLab0039(lab)
    lab.registrar(2, 8, snap, journals)
    outcomes = []

    def start():
        try:
            gate.start_torrent(HASH_A)
            outcomes.append("permitido")
        except ParadaLabRechazada:
            outcomes.append("bloqueado")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: start(), range(8)))

    assert outcomes == ["bloqueado"] * 8
    assert fake.calls == []
    assert lab.estado(8)["estado"] == "registrada"


def test_start_crudo_por_otra_webui_no_comparte_gate_y_bloquea_retirada(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snap, journals)
    lab.ordenar_stop(8)
    assert lab.observar(8)["estado"] == "parada_observada"
    calls = []

    def handler(req):
        if req.url.path == "/api/v2/torrents/start":
            assert parse_qs(req.content.decode("ascii")) == {
                "hashes": [HASH_A],
            }
            calls.append("EXTERNO")
            fake.torrent["state"] = "uploading"
            return httpx.Response(200, text="Ok.")
        return fake.request(req)

    client._transport = httpx.MockTransport(handler)
    fenced = InicioCustodiadoLab0039(lab)
    with pytest.raises(ParadaLabRechazada):
        fenced.start_torrent(HASH_A)
    assert calls == []
    # El uso DIRECTO de qBit no pasa por la barrera VIEWTV:
    client.start_torrent(HASH_A)
    assert calls == ["EXTERNO"]
    assert lab.observar(8)["estado"] == "bloqueada"
    assert not fenced.estado_custodia(8)["autoriza_borrado_fisico"]


def test_worker_real_con_adaptador_prohibe_inicio_custodiado(
    sandbox, start_lab,
):
    _engine, (first, second) = start_lab
    lab, snap, journals, fake, client = setup(sandbox)
    lab.registrar(2, 8, snap, journals)
    starts = []

    def handler(req):
        if req.url.path == "/api/v2/torrents/info":
            tag = req.url.params.get("tag")
            if tag == f"viewtv-descarga-{first}":
                hash_ = HASH_A
            elif tag == f"viewtv-descarga-{second}":
                hash_ = HASH_B
            else:
                raise AssertionError("Tag no autorizado")
            return httpx.Response(200, json=[{
                "hash": hash_, "tags": tag,
                "state": "stoppedDL",
                "save_path": STAGING_PATH,
            }])
        if req.url.path == "/api/v2/torrents/start":
            data = parse_qs(req.content.decode("ascii"), strict_parsing=True)
            starts.append(data["hashes"][0])
            return httpx.Response(200, text="Ok.")
        return fake.request(req)

    client._transport = httpx.MockTransport(handler)
    gate = InicioCustodiadoLab0039(lab)
    assert starter.process_one_start(
        "worker-test", gate,
        allowed_download_id=first, expected_save_path=STAGING_PATH,
    )
    assert starts == []
    assert saved(_engine, first).inicio_estado == "pendiente"
    assert starter.process_one_start(
        "worker-test", gate,
        allowed_download_id=second, expected_save_path=STAGING_PATH,
    )
    assert starts == [HASH_B]
    assert saved(_engine, second).inicio_estado == "iniciada"
    assert lab.estado(8)["estado"] == "registrada"


def test_fence_falla_cerrado_ante_corrupcion_de_sqlite(sandbox):
    lab, snap, journals, fake, _client = setup(sandbox)
    lab.registrar(2, 8, snap, journals)
    gate = InicioCustodiadoLab0039(lab)
    with sqlite3.connect(lab.db) as conn:
        conn.execute("DROP TABLE custodia")
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(HASH_B)
    assert fake.calls == []
