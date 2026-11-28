"""0045: consumo HMAC + reserva NTFS mismo COMMIT durable, SOLO sandbox."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from test_retirement_film_reservation_lab_0044 import (
    KEY,
    NOW,
    fixture_state,
    kwargs,
)
from worker.retirement_authorization_0019 import (
    AutorizacionDenegada,
    consumir_en_transaccion_0045,
    consumir_ticket_una_vez,
)
from worker.retirement_film_reservation_lab_0044 import (
    ReservaFilmFicticia0044,
    ReservaRechazada,
)

pytest_plugins = ("test_qbit_stop_lab_0038",)


def _counts(reservation: ReservaFilmFicticia0044) -> tuple[int, int]:
    with sqlite3.connect(reservation.custodia.db) as con:
        consumed = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE "
            "type='table' AND name='consumos'"
        ).fetchone()[0]
        admin = 0 if not consumed else con.execute(
            "SELECT COUNT(*) FROM consumos"
        ).fetchone()[0]
        films = con.execute(
            "SELECT COUNT(*) FROM reservas_film_0044"
        ).fetchone()[0]
    return admin, films


def test_reserva_y_firma_consumidas_en_unico_commit_0045(sandbox):
    lab, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    assert _counts(lab) == (0, 0)
    result = lab.reservar(**kwargs(ticket, s, j, n))
    assert result["estado"] == "reservada_no_ejecutable"
    assert _counts(lab) == (1, 1)
    with sqlite3.connect(lab.custodia.db) as con:
        joined = con.execute(
            "SELECT a.nonce,a.medio_id,a.descarga_id,"
            "a.prueba_sha256,r.proof FROM consumos a "
            "JOIN reservas_film_0044 r ON r.nonce=a.nonce"
        ).fetchall()
    assert len(joined) == 1
    assert joined[0][:3] == (ticket["desafio"]["nonce"], 2, 8)
    assert joined[0][3] == joined[0][4]
    assert lab.estado(2)["puede_iniciar_unlink"] is False
    assert fake.calls == []


def test_administracion_0019_en_misma_sqlite_impide_doble_consumo(sandbox):
    lab, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    lab.reservar(**kwargs(ticket, s, j, n))
    args = ticket["desafio"]
    with pytest.raises(AutorizacionDenegada):
        consumir_ticket_una_vez(
            ticket, KEY, lab.custodia.db,
            expected_medio=2, expected_download=8,
            expected_proof=args["prueba_sha256"], now=NOW + 1,
        )
    assert _counts(lab) == (1, 1)
    assert fake.calls == []


def test_consumo_previo_0019_en_misma_sqlite_impide_reservar(sandbox):
    lab, ticket, s, j, n, _, _ = fixture_state(sandbox)
    result = consumir_ticket_una_vez(
        ticket, KEY, lab.custodia.db, expected_medio=2,
        expected_download=8,
        expected_proof=ticket["desafio"]["prueba_sha256"],
        now=NOW + 1,
    )
    assert result["autoriza_borrado_fisico"] is False
    assert _counts(lab) == (1, 0)
    with pytest.raises(ReservaRechazada):
        lab.reservar(**kwargs(ticket, s, j, n))
    assert _counts(lab) == (1, 0)


def test_helper_rechaza_conexion_sin_transaccion(sandbox):
    _, ticket, _s, _j, _n, _, _ = fixture_state(sandbox)
    con = sqlite3.connect(":memory:")
    try:
        with pytest.raises(AutorizacionDenegada):
            consumir_en_transaccion_0045(
                con, ticket, KEY, expected_medio=2,
                expected_download=8,
                expected_proof=ticket["desafio"]["prueba_sha256"],
                now=NOW + 1,
            )
        assert not con.in_transaction
    finally:
        con.close()


def test_trigger_que_falla_despues_del_consumo_revierte_ambos(sandbox):
    lab, ticket, s, j, n, _, _ = fixture_state(sandbox)
    with lab.custodia._tx() as con:
        con.execute(
            "CREATE TRIGGER fail_0045 BEFORE INSERT "
            "ON reservas_film_0044 BEGIN "
            "SELECT RAISE(ABORT, 'fallo_ficticio'); END"
        )
    with pytest.raises(ReservaRechazada):
        lab.reservar(**kwargs(ticket, s, j, n))
    assert _counts(lab) == (0, 0)
    with lab.custodia._tx() as con:
        con.execute("DROP TRIGGER fail_0045")
    lab.reservar(**kwargs(ticket, s, j, n))
    assert _counts(lab) == (1, 1)


@pytest.mark.parametrize("sql", (
    "DELETE FROM consumos",
    "UPDATE consumos SET medio_id=77",
    "UPDATE consumos SET descarga_id=77",
    "UPDATE consumos SET prueba_sha256='a' || substr(prueba_sha256,2)",
    "UPDATE custodia SET estado='bloqueada'",
    "UPDATE custodia SET hash='b' || substr(hash,2)",
))
def test_reapertura_bloquea_divergencia_de_diarios(sandbox, sql):
    lab, ticket, s, j, n, _, _ = fixture_state(sandbox)
    lab.reservar(**kwargs(ticket, s, j, n))
    with lab.custodia._tx() as con:
        con.execute(sql)
    with pytest.raises(ReservaRechazada):
        lab.estado(2)


@pytest.mark.parametrize("unique", (
    "medio", "descarga", "torrent_hash", "nonce", "file_id",
))
def test_reserva_fabricada_sin_unicidad_es_rechazada(sandbox, unique):
    from test_qbit_stop_lab_0038 import setup

    lab, _snapshot, _journal, _fake, _client = setup(
        sandbox, state="stoppedUP",
    )
    schema = {
        "medio": "INTEGER", "descarga": "INTEGER",
        "torrent_hash": "TEXT", "nonce": "TEXT",
        "proof": "TEXT", "file_id": "TEXT", "estado": "TEXT",
    }
    definitions = ",".join(
        f"{column} {kind}" + ("" if column == unique else " UNIQUE")
        for column, kind in schema.items()
    )
    with lab._tx() as con:
        con.execute(
            f"CREATE TABLE reservas_film_0044 ({definitions})"
        )
    with pytest.raises(ReservaRechazada):
        ReservaFilmFicticia0044(lab)


def test_nunca_genera_post_real_ni_permite_unlink(sandbox):
    lab, ticket, s, j, n, fake, _ = fixture_state(sandbox)
    result = lab.reservar(**kwargs(ticket, s, j, n))
    assert result["autoriza_borrado_fisico"] is False
    assert result["puede_iniciar_unlink"] is False
    assert result["torrents_reales_modificados"] == 0
    assert result["peliculas_reales_borradas"] == 0
    assert fake.calls == []


def _run_crash(root: Path, *, after_both: bool) -> subprocess.CompletedProcess:
    # El hijo crea SOLO una conexión a SQLite del sandbox TEMP y se mata.
    # Las credenciales y pruebas son valores sintéticos escritos en tests.
    child = """
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
sys.path.insert(0, str(Path.cwd() / 'tests'))

from contextlib import contextmanager
from test_qbit_stop_lab_0038 import setup
from test_retirada_preflight_0018 import base
from test_retirement_film_reservation_lab_0044 import KEY, NOW, exact, kwargs
from worker.retirement_authorization_0019 import (
    firmar_fuera_de_api, preparar_desafio,
)
from worker.retirement_preflight_0018 import evaluar_retiradas
from worker.retirement_film_reservation_lab_0044 import (
    ReservaFilmFicticia0044, prueba_reserva_0044,
)
import worker.retirement_film_reservation_lab_0044 as mod

lab, snap, journals, fake, client = setup(
    Path(sys.argv[1]), state='stoppedUP',
)
ntfs = base()[2]
reservation = ReservaFilmFicticia0044(lab)
proof = prueba_reserva_0044(
    snap, journals, ntfs, medio_id=2, descarga_id=8,
    file_ids=exact(),
)
challenge = preparar_desafio(
    evaluar_retiradas(snap, journals, ntfs)[0],
    download_id=8, prueba_sha256=proof, now=NOW, nonce='a'*32,
)
ticket = firmar_fuera_de_api(
    challenge, KEY, 'RETIRAR MEDIO 2 DESCARGA 8', now=NOW,
)
if sys.argv[2] == 'after_admin':
    original = mod.consumir_en_transaccion_0045
    def die(*args, **kw):
        original(*args, **kw)
        os._exit(84)
    mod.consumir_en_transaccion_0045 = die
else:
    original_tx = lab._tx
    @contextmanager
    def death_tx():
        with original_tx() as conn:
            conn.create_function('kill_0045', 0, lambda: os._exit(85))
            conn.execute(
                'CREATE TEMP TRIGGER kill_after_reserva_0045 '
                'AFTER INSERT ON reservas_film_0044 '
                'BEGIN SELECT kill_0045(); END'
            )
            yield conn
    lab._tx = death_tx
reservation.reservar(**kwargs(ticket, snap, journals, ntfs))
sys.exit(42)
"""
    return subprocess.run(
        [
            sys.executable, "-c", child,
            str(root), "after_both" if after_both else "after_admin",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, timeout=20, check=False,
    )


@pytest.mark.parametrize("after_both", (False, True))
def test_os_exit_entre_consumo_y_commit_es_rollback_completo(
    sandbox, after_both,
):
    reservation, ticket, snap, journals, ntfs, fake, client = fixture_state(
        sandbox,
    )
    crashed = _run_crash(sandbox, after_both=after_both)
    assert crashed.returncode == (85 if after_both else 84), crashed.stderr
    assert _counts(reservation) == (0, 0)
    with pytest.raises(ReservaRechazada):
        reservation.estado(2)
    # El ticket sigue libre porque NINGUNA de las operaciones hizo COMMIT.
    reservation.reservar(**kwargs(ticket, snap, journals, ntfs))
    assert _counts(reservation) == (1, 1)
    assert reservation.estado(2)["autoriza_borrado_fisico"] is False
    assert fake.calls == []
