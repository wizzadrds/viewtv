"""0046: intención START durable ANTES de un POST a qBit exclusivamente mock."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from test_qbit_stop_lab_0038 import setup
from worker.retirement_qbit_start_fence_lab_0039 import InicioCustodiadoLab0039
from worker.retirement_qbit_start_intent_lab_0046 import (
    InicioAmbiguo0046,
    comprobar_inicio_0046,
)
from worker.retirement_qbit_stop_lab_0038 import (
    CustodiaQbitLab0038,
    ParadaLabRechazada,
)

pytest_plugins = ("test_qbit_stop_lab_0038",)

A = "a" * 40
B = "b" * 40
SHA64 = "c" * 64


def _with_start(sandbox, hash_=A, *, handler=None):
    lab, snap, journals, fake, client = setup(sandbox)
    seen = []

    def normal(req):
        if req.url.path == "/api/v2/torrents/start":
            seen.append(req.content.decode("ascii"))
            return httpx.Response(200, text="Ok.")
        return fake.request(req)

    client._transport = httpx.MockTransport(handler or normal)
    gate = InicioCustodiadoLab0039(lab)
    gate.start_torrent(hash_)
    return gate, lab, snap, journals, fake, client, seen


def test_start_confirmado_es_durable_y_no_se_puede_registrar(sandbox):
    gate, lab, snap, journals, _fake, client, sent = _with_start(sandbox)
    assert sent == ["hashes=" + A]
    state = gate.estado_intencion(A)
    assert state == {
        "estado": "confirmada",
        "puede_registrar_retirada": False,
        "puede_borrar_archivos": False,
        "es_aislamiento_qbit_productivo": False,
    }
    reopened = InicioCustodiadoLab0039(CustodiaQbitLab0038(sandbox, client))
    assert reopened.estado_intencion(A) == state
    with pytest.raises(ParadaLabRechazada):
        reopened.start_torrent(A)
    with pytest.raises(ParadaLabRechazada):
        lab.registrar(2, 8, snap, journals)
    assert sent == ["hashes=" + A]


def test_start_de_64_hex_y_mayusculas_canonico(sandbox):
    gate, lab, _, _, _, client, sent = _with_start(sandbox, SHA64.upper())
    assert sent == ["hashes=" + SHA64]
    assert gate.estado_intencion(SHA64.upper())["estado"] == "confirmada"
    new = InicioCustodiadoLab0039(CustodiaQbitLab0038(sandbox, client))
    with pytest.raises(ParadaLabRechazada):
        new.start_torrent(SHA64)


def test_start_de_otro_hash_no_impide_registrar_pelicula(sandbox):
    gate, lab, snap, journals, fake, _, sent = _with_start(sandbox, B)
    lab.registrar(2, 8, snap, journals)
    assert lab.estado(8)["estado"] == "registrada"
    assert gate.estado_intencion(B)["estado"] == "confirmada"
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(A)
    assert sent == ["hashes=" + B]
    assert fake.calls == []


def test_un_error_http_no_pierde_la_intencion_durable(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    calls = []

    def handler(req):
        if req.url.path == "/api/v2/torrents/start":
            calls.append("POST")
            # El cliente no sabe si el servidor aplico START.
            raise httpx.ReadError("Respuesta perdida", request=req)
        return fake.request(req)

    client._transport = httpx.MockTransport(handler)
    gate = InicioCustodiadoLab0039(lab)
    with pytest.raises(Exception):
        gate.start_torrent(A)
    assert calls == ["POST"]
    assert gate.estado_intencion(A)["estado"] == "pendiente"
    with pytest.raises(ParadaLabRechazada):
        lab.registrar(2, 8, snap, journals)
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(A)
    assert calls == ["POST"]


def test_mismo_hash_concurrente_solo_un_post(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    calls = []
    entered = threading.Event()
    release = threading.Event()

    def handler(req):
        if req.url.path == "/api/v2/torrents/start":
            calls.append("POST")
            entered.set()
            assert release.wait(2)
            return httpx.Response(200, text="Ok.")
        return fake.request(req)

    client._transport = httpx.MockTransport(handler)
    gate = InicioCustodiadoLab0039(lab)

    def try_start(_):
        try:
            gate.start_torrent(A)
            return "ok"
        except ParadaLabRechazada:
            return "blocked"

    with ThreadPoolExecutor(max_workers=6) as pool:
        first = pool.submit(try_start, 0)
        assert entered.wait(2)
        others = [pool.submit(try_start, x) for x in range(1, 6)]
        release.set()
        results = [first.result(timeout=4)] + [
            item.result(timeout=4) for item in others
        ]
    assert results.count("ok") == 1
    assert results.count("blocked") == 5
    assert calls == ["POST"]
    assert gate.estado_intencion(A)["estado"] == "confirmada"
    with pytest.raises(ParadaLabRechazada):
        lab.registrar(2, 8, snap, journals)


def test_custodia_primero_impide_crear_intencion(sandbox):
    lab, snap, journals, fake, _client = setup(sandbox)
    lab.registrar(2, 8, snap, journals)
    gate = InicioCustodiadoLab0039(lab)
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(A)
    with pytest.raises(ParadaLabRechazada):
        gate.estado_intencion(A)
    assert fake.calls == []


def test_borrar_tabla_start_no_recrea_custodia_silenciosamente(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    with sqlite3.connect(lab.db) as conn:
        conn.execute("DROP TABLE inicios_qbit_0046")
    with pytest.raises(InicioAmbiguo0046):
        CustodiaQbitLab0038(sandbox, client)
    with pytest.raises(ParadaLabRechazada):
        lab.registrar(2, 8, snap, journals)
    assert fake.calls == []


def test_tabla_start_falsa_sin_pk_rechazada(sandbox):
    lab, _snap, _journals, _fake, client = setup(sandbox)
    with sqlite3.connect(lab.db) as conn:
        conn.execute("DROP TABLE inicios_qbit_0046")
        conn.execute(
            "CREATE TABLE inicios_qbit_0046(hash TEXT,estado TEXT)"
        )
    with pytest.raises(InicioAmbiguo0046):
        CustodiaQbitLab0038(sandbox, client)
    with pytest.raises(InicioAmbiguo0046):
        with lab._tx() as conn:
            comprobar_inicio_0046(conn)


def test_estado_pendiente_vive_en_reaperturas_sin_ttl(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    with lab._tx() as conn:
        conn.execute(
            "INSERT INTO inicios_qbit_0046 VALUES(?,'pendiente')", (A,),
        )
    for _ in range(3):
        custodia = CustodiaQbitLab0038(sandbox, client)
        gate = InicioCustodiadoLab0039(custodia)
        assert gate.estado_intencion(A)["estado"] == "pendiente"
        with pytest.raises(ParadaLabRechazada):
            custodia.registrar(2, 8, snap, journals)
        with pytest.raises(ParadaLabRechazada):
            gate.start_torrent(A)
    assert fake.calls == []


def test_respuesta_incierta_es_barrera_pegajosa(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    with lab._tx() as conn:
        conn.execute(
            "INSERT INTO inicios_qbit_0046 VALUES(?,'respuesta_incierta')",
            (A,),
        )
    new = CustodiaQbitLab0038(sandbox, client)
    with pytest.raises(ParadaLabRechazada):
        new.registrar(2, 8, snap, journals)
    with pytest.raises(ParadaLabRechazada):
        InicioCustodiadoLab0039(new).start_torrent(A)
    assert fake.calls == []


def _child_crash(sandbox: Path, *, during_post: bool) -> subprocess.CompletedProcess:
    child = """
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import httpx

sys.path.insert(0, str(Path.cwd().parent))
sys.path.insert(0, str(Path.cwd() / 'tests'))
from test_qbit_stop_lab_0038 import setup
from worker.retirement_qbit_start_fence_lab_0039 import InicioCustodiadoLab0039

root=Path(sys.argv[1])
lab,snap,journals,fake,client=setup(root)
if sys.argv[2]=='post':
    def handler(req):
        if req.url.path == '/api/v2/torrents/start':
            marker=root/'post-mock-0046.txt'
            fd=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            os.write(fd,b'POST_RECIBIDO_SOLO_MOCK')
            os.fsync(fd)
            os.close(fd)
            os._exit(86)
        return fake.request(req)
    client._transport=httpx.MockTransport(handler)
else:
    original=lab._tx
    counter=[0]
    @contextmanager
    def die_after_commit():
        with original() as conn:
            yield conn
        counter[0]+=1
        if counter[0]==1:
            os._exit(87)
    lab._tx=die_after_commit
InicioCustodiadoLab0039(lab).start_torrent('a'*40)
raise SystemExit(42)
"""
    return subprocess.run(
        [
            sys.executable, "-c", child, str(sandbox),
            "post" if during_post else "before",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, timeout=15, check=False,
    )


@pytest.mark.parametrize("during_post", (False, True))
def test_proceso_muere_y_intencion_sobrevive_antes_o_durante_post(
    sandbox, during_post,
):
    crashed = _child_crash(sandbox, during_post=during_post)
    assert crashed.returncode == (86 if during_post else 87), crashed.stderr
    assert (sandbox / "post-mock-0046.txt").exists() is during_post
    _, snap, journals, fake, client = setup(sandbox)
    lab = CustodiaQbitLab0038(sandbox, client)
    gate = InicioCustodiadoLab0039(lab)
    assert gate.estado_intencion(A)["estado"] == "pendiente"
    with pytest.raises(ParadaLabRechazada):
        lab.registrar(2, 8, snap, journals)
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(A)
    assert fake.calls == []


@pytest.mark.parametrize("bad", ("all", "", "a" * 39, "X" * 40, None, 21))
def test_entrada_peligrosa_no_crea_intencion(sandbox, bad):
    lab, _, _, fake, _ = setup(sandbox)
    gate = InicioCustodiadoLab0039(lab)
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(bad)
    with lab._tx() as con:
        assert con.execute(
            "SELECT COUNT(*) FROM inicios_qbit_0046"
        ).fetchone()[0] == 0
    assert fake.calls == []


def test_falla_cerrado_al_sustituir_transporte_antes_del_post(sandbox):
    lab, snap, journals, fake, client = setup(sandbox)
    gate = InicioCustodiadoLab0039(lab)
    original = lab._tx

    from contextlib import contextmanager

    counter = [0]

    @contextmanager
    def switch_after_commit():
        with original() as conn:
            yield conn
        counter[0] += 1
        if counter[0] == 1:
            client._transport = None

    lab._tx = switch_after_commit
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(A)
    with original() as conn:
        assert conn.execute(
            "SELECT estado FROM inicios_qbit_0046 WHERE hash=?", (A,),
        ).fetchone() == ("pendiente",)
    assert fake.calls == []


def test_corrupt_start_ledger_alterado_falla_cerrado(sandbox):
    lab, _, _, fake, _ = setup(sandbox)
    with sqlite3.connect(lab.db) as con:
        con.execute(
            "INSERT INTO inicios_qbit_0046 VALUES(?,'pendiente')", (A,),
        )
        con.execute("PRAGMA ignore_check_constraints=ON")
        con.execute(
            "UPDATE inicios_qbit_0046 SET estado='inventada' WHERE hash=?",
            (A,),
        )
    gate = InicioCustodiadoLab0039(lab)
    with pytest.raises(ParadaLabRechazada):
        gate.start_torrent(B)
    assert fake.calls == []
