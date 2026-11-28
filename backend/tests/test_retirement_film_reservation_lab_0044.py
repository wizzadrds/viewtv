"""0044: ticket administrativo ligado a un unico File ID ficticio y qBit mock."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from test_qbit_stop_lab_0038 import setup
from test_retirada_preflight_0018 import base
from worker.retirement_authorization_0019 import (
    firmar_fuera_de_api,
    preparar_desafio,
)
from worker.retirement_film_reservation_lab_0044 import (
    ReservaFilmFicticia0044,
    ReservaRechazada,
    prueba_reserva_0044,
)
from worker.retirement_preflight_0018 import evaluar_retiradas
from worker.retirement_qbit_stop_lab_0038 import CustodiaQbitLab0038

pytest_plugins = ("test_qbit_stop_lab_0038",)

KEY = b"K" * 32
NOW = 1_800_000_000
FILE = {
    "volume": 128, "file_index_high": 0, "file_index_low": 846,
    "hardlinks": 2, "size_bytes": 1024, "sha256": "f" * 64,
}


def exact():
    return {"original": dict(FILE), "publicado": dict(FILE)}


def fixture_state(sandbox, *, observed=True):
    lab, snapshot, journal, fake, client = setup(
        sandbox, state="stoppedUP",
    )
    _, _, ntfs = base()
    lab.registrar(2, 8, snapshot, journal)
    if observed:
        lab.ordenar_stop(8)
        assert lab.observar(8)["estado"] == "parada_observada"
    proof = prueba_reserva_0044(
        snapshot, journal, ntfs, medio_id=2, descarga_id=8,
        file_ids=exact(),
    )
    rows = evaluar_retiradas(snapshot, journal, ntfs)
    challenge = preparar_desafio(
        rows[0], download_id=8, prueba_sha256=proof,
        now=NOW, nonce="a" * 32,
    )
    ticket = firmar_fuera_de_api(
        challenge, KEY, "RETIRAR MEDIO 2 DESCARGA 8", now=NOW,
    )
    reservation = ReservaFilmFicticia0044(lab)
    return reservation, ticket, snapshot, journal, ntfs, fake, client


def kwargs(ticket, snapshot, journal, ntfs):
    return dict(
        ticket=ticket, key=KEY,
        snapshot_inicial=snapshot, snapshot_final=deepcopy(snapshot),
        journals=journal, ntfs=ntfs, file_ids=exact(),
        medio_id=2, descarga_id=8, now=NOW + 1,
    )


def test_reserva_unica_film_id_y_ticket_para_ensayo(sandbox):
    reservation, ticket, snapshot, journal, ntfs, fake, client = fixture_state(
        sandbox,
    )
    verdict = reservation.reservar(**kwargs(ticket, snapshot, journal, ntfs))
    assert verdict["estado"] == "reservada_no_ejecutable"
    assert verdict["ticket_consumido_para_ensayo"] is True
    assert verdict["puede_iniciar_unlink"] is False
    assert verdict["autoriza_borrado_fisico"] is False
    assert verdict["torrents_reales_modificados"] == 0
    assert verdict["peliculas_reales_borradas"] == 0
    assert fake.calls == []
    reopened = ReservaFilmFicticia0044(CustodiaQbitLab0038(sandbox, client))
    assert reopened.estado(2)["estado"] == "reservada_no_ejecutable"
    assert reopened.estado(2)["autoriza_borrado_fisico"] is False


def test_ticket_consumido_no_se_admite_por_segunda_vez(sandbox):
    reservation, ticket, s, j, n, _, _ = fixture_state(sandbox)
    args = kwargs(ticket, s, j, n)
    reservation.reservar(**args)
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**args)


def test_nuevo_nonce_firmado_para_misma_pelicula_tampoco_se_admite(sandbox):
    reservation, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    reservation.reservar(**kwargs(ticket, s, j, n))
    replacement = deepcopy(ticket["desafio"])
    replacement["nonce"] = "b" * 32
    second = firmar_fuera_de_api(
        replacement, KEY, "RETIRAR MEDIO 2 DESCARGA 8", now=NOW,
    )
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(second, s, j, n))
    assert fake.calls == []


def test_ticket_firmado_con_huella_0019_sin_file_id_no_vale(sandbox):
    from worker.retirement_authorization_0019 import (
        huella_evidencias_completas,
    )

    reservation, ticket, s, j, n, _, _ = fixture_state(sandbox)
    bogus = deepcopy(ticket["desafio"])
    bogus["prueba_sha256"] = huella_evidencias_completas(
        s, j, n, medio_id=2, descarga_id=8,
    )
    bad_ticket = firmar_fuera_de_api(
        bogus, KEY, "RETIRAR MEDIO 2 DESCARGA 8", now=NOW,
    )
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(bad_ticket, s, j, n))


@pytest.mark.parametrize("mutation", (
    lambda proof: proof["publicado"].update(file_index_low=847),
    lambda proof: proof["original"].update(hardlinks=3),
    lambda proof: proof["publicado"].update(hardlinks=1),
    lambda proof: proof["original"].update(size_bytes=1025),
    lambda proof: proof["original"].update(sha256="g" * 64),
    lambda proof: proof["original"].update(volume=-1),
    lambda proof: proof["publicado"].update(file_index_high=2**32),
    lambda proof: proof["original"].update(file_index_low=True),
    lambda proof: proof["original"].update(size_bytes=0),
    lambda proof: proof["original"].update(extra="secreto"),
    lambda proof: proof.update(tercero=dict(FILE)),
    lambda proof: proof.pop("publicado"),
))
def test_file_id_o_tres_enlaces_invalidados(sandbox, mutation):
    reservation, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    bad = exact()
    mutation(bad)
    args = kwargs(ticket, s, j, n)
    args["file_ids"] = bad
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**args)
    assert fake.calls == []


@pytest.mark.parametrize("mutation", (
    lambda snapshot: snapshot["qbittorrent"]["8"]["torrent"].update(state="uploading"),
    lambda snapshot: snapshot["qbittorrent"]["8"]["torrent"].update(progress=0.5),
    lambda snapshot: snapshot["qbittorrent"]["8"]["files"][0].update(size=1025),
    lambda snapshot: snapshot["peliculas"][0].update(visto_perfiles=[1]),
    lambda snapshot: snapshot["peliculas"][0].update(pendiente_perfiles=[]),
    lambda snapshot: snapshot["peliculas"][0].update(tmdb_id=9000),
    lambda snapshot: snapshot["jellyfin"]["elementos"][0].update(path="/media/otra.mkv"),
))
def test_evidencia_cambiada_desde_la_firma_no_se_reserva(sandbox, mutation):
    reservation, ticket, s, j, n, _, _ = fixture_state(sandbox)
    end = deepcopy(s)
    mutation(end)
    args = kwargs(ticket, s, j, n)
    args["snapshot_final"] = end
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**args)


@pytest.mark.parametrize("value", (0, -1, True, 2**31, "2", None))
def test_id_de_medio_no_verificable_bloquea(sandbox, value):
    reservation, ticket, s, j, n, _, _ = fixture_state(sandbox)
    args = kwargs(ticket, s, j, n)
    args["medio_id"] = value
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**args)


@pytest.mark.parametrize("change", (
    {"now": NOW + 600},
    {"now": NOW - 2},
    {"key": b"Q" * 32},
    {"medio_id": 3},
    {"descarga_id": 9},
))
def test_token_invalido_otro_medio_o_fuera_de_tiempo_bloquea(sandbox, change):
    reservation, ticket, s, j, n, _, _ = fixture_state(sandbox)
    args = kwargs(ticket, s, j, n)
    args.update(change)
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**args)


def test_no_se_reserva_si_qbit_no_tiene_parada_observada(sandbox):
    reservation, ticket, s, j, n, _, _ = fixture_state(
        sandbox, observed=False,
    )
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(ticket, s, j, n))


@pytest.mark.parametrize("state", ("orden_pendiente", "bloqueada", "orden_enviada"))
def test_no_se_reserva_con_estado_qbit_no_estable(sandbox, state):
    reservation, ticket, s, j, n, _, _ = fixture_state(sandbox)
    with reservation.custodia._tx() as db:
        db.execute(
            "UPDATE custodia SET estado=? WHERE descarga=8", (state,),
        )
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(ticket, s, j, n))


def test_16_reservas_concurrentes_un_solo_ganador(sandbox):
    reservation, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    args = kwargs(ticket, s, j, n)

    def attempt(_):
        try:
            reservation.reservar(**args)
            return True
        except ReservaRechazada:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        result = list(pool.map(attempt, range(16)))
    assert result.count(True) == 1
    assert result.count(False) == 15
    assert fake.calls == []


def test_sqlite_en_estado_bloqueado_falla_cerrada(sandbox):
    reservation, ticket, s, j, n, _, _ = fixture_state(sandbox)
    with sqlite3.connect(reservation.custodia.db) as conn:
        conn.execute("DROP TABLE custodia")
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(ticket, s, j, n))


def test_no_se_reserva_con_diario_qbit_ajeno_a_pelicula(sandbox):
    reservation, ticket, s, j, n, _, _ = fixture_state(sandbox)
    with reservation.custodia._tx() as conn:
        conn.execute("UPDATE custodia SET medio=7 WHERE descarga=8")
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(ticket, s, j, n))


def test_repeticion_despues_de_cerrar_y_reabrir_reserva(sandbox):
    reservation, ticket, s, j, n, _, client = fixture_state(sandbox)
    reservation.reservar(**kwargs(ticket, s, j, n))
    reopened = ReservaFilmFicticia0044(CustodiaQbitLab0038(sandbox, client))
    with pytest.raises(ReservaRechazada):
        reopened.reservar(**kwargs(ticket, s, j, n))


@pytest.mark.parametrize("wrong", (
    {"original": FILE},
    {},
    None,
    123,
    "C:/VIEWTV/Peliculas/real.mkv",
))
def test_no_se_permiten_pruebas_ntfs_incompletas(sandbox, wrong):
    reservation, ticket, s, j, n, _, _ = fixture_state(sandbox)
    args = kwargs(ticket, s, j, n)
    args["file_ids"] = wrong
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**args)


def test_webui_externa_reanuda_antes_de_reserva_y_se_rechaza(sandbox):
    reservation, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    # El estado SQLite sigue diciendo parada_observada.
    fake.torrent["state"] = "uploading"
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(ticket, s, j, n))
    assert reservation.custodia.estado(8)["estado"] == "parada_observada"


def test_qbit_cambia_archivo_auxiliar_fuera_de_laboratorio(sandbox):
    reservation, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    fake.files[0]["size"] = 1025
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(ticket, s, j, n))


def test_mock_transport_no_puede_mutarse_a_transporte_real(sandbox):
    reservation, ticket, s, j, n, _, client = fixture_state(sandbox)
    client._transport = None
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(ticket, s, j, n))


def test_reanudacion_entre_dos_lecturas_qbit_falla_cerrada(sandbox):
    reservation, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    fake.resumed_on_info = True
    with pytest.raises(ReservaRechazada):
        reservation.reservar(**kwargs(ticket, s, j, n))


def test_cerco_0039_no_reinicia_hash_una_vez_reservado(sandbox):
    from worker.retirement_qbit_start_fence_lab_0039 import (
        InicioCustodiadoLab0039,
    )
    from worker.retirement_qbit_stop_lab_0038 import ParadaLabRechazada

    reservation, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    reservation.reservar(**kwargs(ticket, s, j, n))
    fence = InicioCustodiadoLab0039(reservation.custodia)
    with pytest.raises(ParadaLabRechazada):
        fence.start_torrent("a" * 40)
    assert fake.calls == []
    assert not reservation.estado(2)["puede_iniciar_unlink"]


def test_muerte_real_de_proceso_despues_consumo_no_reautoriza(sandbox):
    """SQLite mantiene UNIQUE por medio incluso tras os._exit(83)."""
    import subprocess
    import sys
    from pathlib import Path

    child = """
import os
import sys
from pathlib import Path

cwd = Path.cwd()
sys.path.insert(0, str(cwd.parent))
sys.path.insert(0, str(cwd / 'tests'))
from test_retirement_film_reservation_lab_0044 import fixture_state, kwargs

reservation, ticket, snapshot, journals, ntfs, _, _ = fixture_state(
    Path(sys.argv[1]),
)
reservation.reservar(**kwargs(ticket, snapshot, journals, ntfs))
os._exit(83)
"""
    proc = subprocess.run(
        [sys.executable, "-c", child, str(sandbox)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert proc.returncode == 83, proc.stderr

    # Tras crash, otra instancia de qBit totalmente ficticia reabre el
    # mismo SQLite, con una firma distinta para la MISMA película.
    lab, s, j, fake, client = setup(sandbox, state="stoppedUP")
    reopened = ReservaFilmFicticia0044(lab)
    assert reopened.estado(2)["estado"] == "reservada_no_ejecutable"
    _, _, ntfs = base()
    proof = prueba_reserva_0044(
        s, j, ntfs, medio_id=2, descarga_id=8, file_ids=exact(),
    )
    rows = evaluar_retiradas(s, j, ntfs)
    challenge = preparar_desafio(
        rows[0], download_id=8, prueba_sha256=proof,
        now=NOW, nonce="b" * 32,
    )
    second = firmar_fuera_de_api(
        challenge, KEY, "RETIRAR MEDIO 2 DESCARGA 8", now=NOW,
    )
    with pytest.raises(ReservaRechazada):
        reopened.reservar(**kwargs(second, s, j, ntfs))
    assert reopened.estado(2)["autoriza_borrado_fisico"] is False
    assert fake.calls == []
