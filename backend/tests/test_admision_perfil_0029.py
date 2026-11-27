"""0029 — sesión y lectura de vídeo ligadas a un perfil en TEMP ficticio."""
from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
from worker.retirement_playback_admission_0027 import (
    MARKER,
    AdmisionRechazada,
)
from worker.retirement_profile_admission_0029 import AdmisionPerfilLab0029


@pytest.fixture
def lab():
    root = Path(tempfile.gettempdir()) / (
        "viewtv-admission-0027-" + uuid.uuid4().hex
    )
    root.mkdir(mode=0o700)
    marker = root / "marca-0027.txt"
    fd = os.open(
        marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY
        | getattr(os, "O_NOFOLLOW", 0), 0o600,
    )
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(MARKER)
    try:
        yield AdmisionPerfilLab0029(root)
    finally:
        shutil.rmtree(root)


def test_sesion_privada_atribuida_a_perfil_y_drenaje(lab):
    ticket = lab.abrir_para_perfil(4, 17)
    io = lab.empezar_lectura(4, 17, ticket)
    assert lab.iniciar_drenaje(4)["estado"] == "drenando"
    lab.cerrar_para_perfil(4, 17, ticket)
    assert lab.observar(4)["peticiones_video_pendientes"] == 1
    lab.terminar_lectura(4, 17, ticket, io)
    assert lab.observar(4)["estado"] == "listo_para_preflight"
    assert lab.observar_agregado(4) == {
        "estado": "listo_para_preflight",
        "sesiones_pendientes": 0,
        "peticiones_video_pendientes": 0,
        "perfiles_identificados": True,
        "jellyfin_externo_controlado": False,
        "qbittorrent_controlado": False,
        "autoriza_borrado_fisico": False,
    }


def test_otro_perfil_no_puede_iniciar_leer_ni_cerrar_sesion_ajena(lab):
    ticket = lab.abrir_para_perfil(4, 17)
    with pytest.raises(AdmisionRechazada):
        lab.empezar_lectura(4, 18, ticket)
    with pytest.raises(AdmisionRechazada):
        lab.cerrar_para_perfil(4, 18, ticket)
    io = lab.empezar_lectura(4, 17, ticket)
    with pytest.raises(AdmisionRechazada):
        lab.terminar_lectura(4, 18, ticket, io)
    assert lab.iniciar_drenaje(4)["estado"] == "drenando"
    assert lab.observar(4)["peticiones_video_pendientes"] == 1
    lab.cerrar_para_perfil(4, 17, ticket)
    lab.terminar_lectura(4, 17, ticket, io)
    assert lab.observar(4)["estado"] == "listo_para_preflight"


def test_sesion_de_otra_pelicula_no_se_puede_reutilizar(lab):
    ticket = lab.abrir_para_perfil(4, 17)
    with pytest.raises(AdmisionRechazada):
        lab.empezar_lectura(5, 17, ticket)
    with pytest.raises(AdmisionRechazada):
        lab.cerrar_para_perfil(5, 17, ticket)
    lab.cerrar_para_perfil(4, 17, ticket)


def test_drenaje_rechaza_nueva_sesion_sin_borrar_perfiles(lab):
    ticket1 = lab.abrir_para_perfil(4, 17)
    ticket2 = lab.abrir_para_perfil(4, 18)
    assert lab.iniciar_drenaje(4)["estado"] == "drenando"
    for profile in (17, 18):
        with pytest.raises(AdmisionRechazada):
            lab.abrir_para_perfil(4, profile)
    lab.cerrar_para_perfil(4, 17, ticket1)
    assert lab.observar(4)["estado"] == "drenando"
    lab.cerrar_para_perfil(4, 18, ticket2)
    assert lab.observar(4)["estado"] == "listo_para_preflight"


@pytest.mark.parametrize("invalid", [None, True, 0, -1, "1", 1.0, 2_147_483_648])
def test_perfiles_invalidos_fallan_cerrado(lab, invalid):
    with pytest.raises(AdmisionRechazada):
        lab.abrir_para_perfil(4, invalid)


def test_registro_no_expira_cuando_se_pierde_una_lectura(lab):
    ticket = lab.abrir_para_perfil(4, 17)
    io = lab.empezar_lectura(4, 17, ticket)
    lab.cerrar_para_perfil(4, 17, ticket)
    lab2 = AdmisionPerfilLab0029(lab.root)
    assert lab2.iniciar_drenaje(4)["estado"] == "drenando"
    assert lab2.observar(4)["peticiones_video_pendientes"] == 1
    lab2.terminar_lectura(4, 17, ticket, io)
    assert lab2.observar(4)["autoriza_borrado_fisico"] is False
    assert lab2.observar(4)["estado"] == "listo_para_preflight"


def test_replay_de_token_cerrado_es_denegado(lab):
    ticket = lab.abrir_para_perfil(4, 17)
    request = lab.empezar_lectura(4, 17, ticket)
    lab.terminar_lectura(4, 17, ticket, request)
    lab.cerrar_para_perfil(4, 17, ticket)
    with pytest.raises(AdmisionRechazada):
        lab.cerrar_para_perfil(4, 17, ticket)
    with pytest.raises(AdmisionRechazada):
        lab.empezar_lectura(4, 17, ticket)
    with pytest.raises(AdmisionRechazada):
        lab.terminar_lectura(4, 17, ticket, request)


def test_informe_no_contiene_tokens_ni_identidad(lab):
    ticket = lab.abrir_para_perfil(4, 123456)
    summary = lab.observar_agregado(4)
    assert "123456" not in str(summary)
    assert ticket not in str(summary)
    assert summary["sesiones_pendientes"] == 1
    assert summary["autoriza_borrado_fisico"] is False


def test_fuera_de_sandbox_sigue_prohibido(tmp_path):
    with pytest.raises(AdmisionRechazada):
        AdmisionPerfilLab0029(tmp_path)
