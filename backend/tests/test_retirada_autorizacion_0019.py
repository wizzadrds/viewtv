"""Autorización administrativa exclusivamente con identidades ficticias.

Nunca utiliza un perfil real, un PIN, un token de sesión, medios ni
diarios del publicador; clave y SQLite de consumo viven en tmp_path.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

import pytest
from test_retirada_preflight_0018 import base
from worker.retirement_authorization_0019 import (
    AutorizacionDenegada,
    consumir_ticket_una_vez,
    firmar_fuera_de_api,
    huella_evidencias_completas,
    leer_clave_administrador,
    preparar_desafio,
    preparar_desafio_de_evidencias,
    verificar_ticket,
)

KEY = b"A" * 32
OTHER_KEY = b"B" * 32
NOW = 1_800_000_000
PROOF = "c" * 64
IDEAL = {
    "medio_id": 9,
    "estado": "bloqueada",
    "puede_borrarse_ahora": False,
    "motivos": ["falta_autorizacion_administrador"],
}


def sample() -> tuple[dict, dict]:
    challenge = preparar_desafio(
        IDEAL,
        download_id=8,
        prueba_sha256=PROOF,
        now=NOW,
        nonce="d" * 32,
    )
    ticket = firmar_fuera_de_api(
        challenge, KEY, "RETIRAR MEDIO 9 DESCARGA 8", now=NOW,
    )
    return challenge, ticket


def verify(ticket: dict, **changes) -> bool:
    kwargs = {
        "expected_medio": 9,
        "expected_download": 8,
        "expected_proof": PROOF,
        "now": NOW + 1,
    }
    kwargs.update(changes)
    return verificar_ticket(ticket, KEY, **kwargs)


def test_ticket_exactamente_vinculado_a_una_pelicula_y_manifesto():
    challenge, ticket = sample()
    assert challenge["version"] == 1
    assert challenge["vence_epoch"] == NOW + 600
    assert len(ticket["firma"]) == 64
    assert "pin" not in str(ticket).lower()
    assert verify(ticket) is True
    assert sample() == (challenge, ticket)


@pytest.mark.parametrize(("field", "value"), [
    ("medio_id", 10),
    ("descarga_id", 10),
    ("prueba_sha256", "0" * 64),
    ("nonce", "0" * 32),
    ("vence_epoch", NOW - 1),
    ("accion", "retirar_todo"),
    ("version", 999),
])
def test_manipular_desafio_firmado_rechazado(field, value):
    _, ticket = sample()
    ticket["desafio"][field] = value
    with pytest.raises(AutorizacionDenegada):
        verify(ticket)


def test_firma_falsa_y_clave_distinta_son_rechazadas():
    _, ticket = sample()
    changed = deepcopy(ticket)
    changed["firma"] = "a" * 64
    with pytest.raises(AutorizacionDenegada):
        verify(changed)
    with pytest.raises(AutorizacionDenegada):
        verificar_ticket(
            ticket, OTHER_KEY,
            expected_medio=9, expected_download=8,
            expected_proof=PROOF, now=NOW,
        )


@pytest.mark.parametrize("kwargs", [
    {"expected_medio": 1},
    {"expected_download": 11},
    {"expected_proof": "f" * 64},
    {"now": NOW + 600},
    {"now": NOW - 2},
])
def test_ticket_no_sirve_para_otra_pelicula_otro_snapshot_ni_otra_fecha(kwargs):
    _, ticket = sample()
    # Tiempo anterior solo se deniega si excede validez máxima permitida.
    if kwargs == {"now": NOW - 2}:
        kwargs["now"] = NOW - 5
    with pytest.raises(AutorizacionDenegada):
        verify(ticket, **kwargs)


@pytest.mark.parametrize("bad", [
    {"medio_id": 9, "estado": "apta", "puede_borrarse_ahora": True,
     "motivos": []},
    {"medio_id": 9, "estado": "bloqueada", "puede_borrarse_ahora": False,
     "motivos": ["torrent_activo_o_incompleto", "falta_autorizacion_administrador"]},
    {"medio_id": 9, "estado": "bloqueada", "puede_borrarse_ahora": False,
     "motivos": ["sin_publicacion_unica"]},
    {"medio_id": 9, "estado": "bloqueada", "puede_borrarse_ahora": False,
     "motivos": []},
])
def test_perfil_visto_o_torrent_activo_no_permita_solicitar_aprobacion(bad):
    with pytest.raises(AutorizacionDenegada):
        preparar_desafio(bad, download_id=8, prueba_sha256=PROOF, now=NOW)


@pytest.mark.parametrize("confirmacion", [
    "", "RETIRAR TODO", "RETIRAR MEDIO 10 DESCARGA 8",
    "RETIRAR MEDIO 9 DESCARGA 7", "retirar medio 9 descarga 8",
])
def test_firma_requiere_confirmacion_muy_especifica(confirmacion):
    challenge, _ = sample()
    with pytest.raises(AutorizacionDenegada):
        firmar_fuera_de_api(challenge, KEY, confirmacion, now=NOW)


def test_no_permite_secreto_corto_o_tipo_equivocado():
    challenge, ticket = sample()
    for invalid in (b"", b"x" * 16, b"0" * 33, "x" * 32):
        with pytest.raises(AutorizacionDenegada):
            firmar_fuera_de_api(
                challenge, invalid, "RETIRAR MEDIO 9 DESCARGA 8", now=NOW,
            )
        with pytest.raises(AutorizacionDenegada):
            verificar_ticket(
                ticket, invalid, expected_medio=9, expected_download=8,
                expected_proof=PROOF, now=NOW,
            )


def test_clave_solo_de_directorio_propio_sin_symlinks(tmp_path):
    own = tmp_path / "administrador"
    own.mkdir(mode=0o700)
    keyfile = own / "clave.bin"
    keyfile.write_bytes(KEY)
    keyfile.chmod(0o600)
    assert leer_clave_administrador(keyfile) == KEY
    keyfile.chmod(0o644)
    with pytest.raises(AutorizacionDenegada):
        leer_clave_administrador(keyfile)
    keyfile.chmod(0o600)
    alias = own / "alias"
    alias.symlink_to(keyfile)
    with pytest.raises(AutorizacionDenegada):
        leer_clave_administrador(alias)
    own.chmod(0o777)
    with pytest.raises(AutorizacionDenegada):
        leer_clave_administrador(keyfile)


def test_se_acepta_un_consumo_no_dos(tmp_path):
    folder = tmp_path / "admin-ledger"
    folder.mkdir(mode=0o700)
    ledger = folder / "consumos.db"
    _, ticket = sample()
    kwargs = {
        "expected_medio": 9, "expected_download": 8,
        "expected_proof": PROOF, "now": NOW + 1,
    }
    result = consumir_ticket_una_vez(ticket, KEY, ledger, **kwargs)
    assert result["estado"] == "consumida_para_ensayo"
    assert result["autoriza_borrado_fisico"] is False
    assert Path(ledger).stat().st_mode & 0o077 == 0
    with pytest.raises(AutorizacionDenegada):
        consumir_ticket_una_vez(ticket, KEY, ledger, **kwargs)


def test_consumo_concurrente_tiene_un_solo_ganador(tmp_path):
    folder = tmp_path / "admin-ledger"
    folder.mkdir(mode=0o700)
    _, ticket = sample()
    ledger = folder / "consumos.db"

    def attempt(_):
        try:
            return consumir_ticket_una_vez(
                ticket, KEY, ledger,
                expected_medio=9, expected_download=8,
                expected_proof=PROOF, now=NOW + 1,
            )["estado"]
        except AutorizacionDenegada:
            return "rechazada"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(16)))
    assert results.count("consumida_para_ensayo") == 1
    assert results.count("rechazada") == 15


def test_diario_fuera_de_directorio_privado_o_symlink_bloquea(tmp_path):
    folder = tmp_path / "publico"
    folder.mkdir(mode=0o777)
    folder.chmod(0o777)
    _, ticket = sample()
    kwargs = {
        "expected_medio": 9, "expected_download": 8,
        "expected_proof": PROOF, "now": NOW + 1,
    }
    with pytest.raises(AutorizacionDenegada):
        consumir_ticket_una_vez(ticket, KEY, folder / "consumos.db", **kwargs)
    assert not (folder / "consumos.db").exists()
    own = tmp_path / "privada"
    own.mkdir(mode=0o700)
    outside = tmp_path / "fuera.db"
    outside.touch()
    (own / "consumos.db").symlink_to(outside)
    with pytest.raises(AutorizacionDenegada):
        consumir_ticket_una_vez(ticket, KEY, own / "consumos.db", **kwargs)
    assert outside.stat().st_size == 0


def test_nunca_se_habilita_borrado_aunque_el_ticket_sea_valido():
    _, ticket = sample()
    assert verify(ticket)
    assert "autoriza_borrado_fisico" not in ticket
    assert "borrar" not in ticket


def test_huella_cuando_cada_origen_es_verificable_y_bloqueo_admin_unico():
    snapshot, journals, ntfs = base()
    digest = huella_evidencias_completas(
        snapshot, journals, ntfs, medio_id=2, descarga_id=8,
    )
    assert isinstance(digest, str)
    assert len(digest) == 64
    assert digest == huella_evidencias_completas(
        deepcopy(snapshot), deepcopy(journals), deepcopy(ntfs),
        medio_id=2, descarga_id=8,
    )


@pytest.mark.parametrize("mutation", [
    "torrent_activo", "sin_visto", "sin_peticion",
    "otro_diario", "otro_hash", "otro_medio", "otra_descarga", "huella_ntfs",
])
def test_huella_solo_si_todo_lo_demas_esta_verificado(mutation):
    snapshot, journals, ntfs = base()
    if mutation == "torrent_activo":
        snapshot["qbittorrent"]["8"]["torrent"]["state"] = "uploading"
    elif mutation == "sin_visto":
        snapshot["peliculas"][0]["visto_perfiles"] = [1]
    elif mutation == "sin_peticion":
        snapshot["peliculas"][0]["pendiente_perfiles"] = []
    elif mutation == "otro_diario":
        journals[8][0]["folder"] = "Otro"
    elif mutation == "otro_hash":
        snapshot["descargas"][0]["hash"] = "b" * 40
    elif mutation == "otro_medio":
        snapshot["peliculas"][0]["medio_id"] = 3
    elif mutation == "otra_descarga":
        journals[8][0]["download_id"] = 9
    elif mutation == "huella_ntfs":
        ntfs[0]["journal_sha256"] = "a" * 64
    with pytest.raises(AutorizacionDenegada):
        huella_evidencias_completas(
            snapshot, journals, ntfs, medio_id=2, descarga_id=8,
        )


def test_desafio_y_ticket_ligados_a_la_misma_pelicula_y_pruebas():
    snapshot, journals, ntfs = base()
    proof = huella_evidencias_completas(
        snapshot, journals, ntfs, medio_id=2, descarga_id=8,
    )
    challenge = preparar_desafio_de_evidencias(
        snapshot, journals, ntfs, medio_id=2, descarga_id=8, now=NOW,
    )
    assert challenge["medio_id"] == 2
    assert challenge["descarga_id"] == 8
    assert challenge["prueba_sha256"] == proof
    ticket = firmar_fuera_de_api(
        challenge, KEY, "RETIRAR MEDIO 2 DESCARGA 8", now=NOW,
    )
    assert verificar_ticket(
        ticket, KEY, expected_medio=2, expected_download=8,
        expected_proof=proof, now=NOW,
    )
    with pytest.raises(AutorizacionDenegada):
        verificar_ticket(
            ticket, KEY, expected_medio=9, expected_download=8,
            expected_proof=proof, now=NOW,
        )
    snapshot["qbittorrent"]["8"]["torrent"]["progress"] = 0.1
    with pytest.raises(AutorizacionDenegada):
        preparar_desafio_de_evidencias(
            snapshot, journals, ntfs, medio_id=2, descarga_id=8, now=NOW,
        )
