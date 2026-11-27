"""0027: exclusión SQLite real entre procesos, SOLO en TEMP sintético.

La salida 'listo_para_preflight' nunca significa autorización de borrado:
Jellyfin externo, qBit y Windows no participan en esta base de pruebas.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from worker.retirement_playback_admission_0027 import (
    MARKER,
    AdmisionRechazada,
    LaboratorioAdmision0027,
)


@pytest.fixture
def lab():
    root = Path(tempfile.gettempdir()) / (
        "viewtv-admission-0027-" + uuid.uuid4().hex
    )
    root.mkdir(mode=0o700)
    marker = root / "marca-0027.txt"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(marker, flags, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as stream:
        stream.write(MARKER)
    try:
        yield LaboratorioAdmision0027(root)
    finally:
        shutil.rmtree(root)


def test_sin_sesiones_un_drenaje_no_autoriza_borrado(lab):
    result = lab.iniciar_drenaje(4)
    assert result == {
        "estado": "listo_para_preflight",
        "no_hay_sesiones_viewtv": True,
        "jellyfin_externo_controlado": False,
        "qbit_controlado": False,
        "autoriza_borrado_fisico": False,
    }
    with pytest.raises(AdmisionRechazada):
        lab.abrir_sesion(4)
    assert lab.iniciar_drenaje(4) == result


def test_sesion_existente_se_drena_sin_expiracion_automatica(lab):
    ticket = lab.abrir_sesion(4)
    assert len(ticket) == 48
    assert lab.iniciar_drenaje(4)["estado"] == "drenando"
    assert lab.observar(4)["sesiones_viewtv_pendientes"] == 1
    with pytest.raises(AdmisionRechazada):
        lab.abrir_sesion(4)
    io = lab.iniciar_peticion(4, ticket)
    lab.cerrar_sesion(4, ticket)
    report = lab.observar(4)
    assert report["estado"] == "drenando"
    assert report["peticiones_video_pendientes"] == 1
    with pytest.raises(AdmisionRechazada):
        lab.iniciar_peticion(4, ticket)
    lab.terminar_peticion(4, ticket, io)
    report = lab.observar(4)
    assert report["estado"] == "listo_para_preflight"
    assert report["sesiones_viewtv_pendientes"] == 0
    assert report["peticiones_video_pendientes"] == 0
    assert report["autoriza_borrado_fisico"] is False


def test_segmento_hls_firmado_no_sustituye_sesion_activa(lab):
    token = lab.abrir_sesion(4)
    io = lab.iniciar_peticion(4, token)
    lab.terminar_peticion(4, token, io)
    lab.cerrar_sesion(4, token)
    with pytest.raises(AdmisionRechazada):
        lab.iniciar_peticion(4, token)
    assert lab.iniciar_drenaje(4)["no_hay_sesiones_viewtv"] is True


def test_sesion_de_otra_pelicula_no_puede_abrir_segmentos(lab):
    token = lab.abrir_sesion(4)
    with pytest.raises(AdmisionRechazada):
        lab.iniciar_peticion(5, token)
    with pytest.raises(AdmisionRechazada):
        lab.cerrar_sesion(5, token)
    assert lab.observar(4)["sesiones_viewtv_pendientes"] == 1
    lab.cerrar_sesion(4, token)


def test_stream_en_curso_protege_aunque_ventana_ya_haya_cerrado(lab):
    token = lab.abrir_sesion(4)
    requests = [lab.iniciar_peticion(4, token) for _ in range(8)]
    lab.cerrar_sesion(4, token)
    assert lab.iniciar_drenaje(4)["estado"] == "drenando"
    for io in requests[:-1]:
        lab.terminar_peticion(4, token, io)
    assert lab.observar(4)["estado"] == "drenando"
    lab.terminar_peticion(4, token, requests[-1])
    assert lab.observar(4)["estado"] == "listo_para_preflight"


def test_repetir_finalizacion_o_usar_token_replay_se_rechaza(lab):
    token = lab.abrir_sesion(4)
    io = lab.iniciar_peticion(4, token)
    lab.terminar_peticion(4, token, io)
    with pytest.raises(AdmisionRechazada):
        lab.terminar_peticion(4, token, io)
    lab.cerrar_sesion(4, token)
    with pytest.raises(AdmisionRechazada):
        lab.cerrar_sesion(4, token)
    with pytest.raises(AdmisionRechazada):
        lab.iniciar_peticion(4, token)


@pytest.mark.parametrize("invalid", [None, True, 0, -1, "4", 1.0, 2_147_483_648])
def test_medios_invalidos_fallan_cerrado(lab, invalid):
    with pytest.raises(AdmisionRechazada):
        lab.abrir_sesion(invalid)
    with pytest.raises(AdmisionRechazada):
        lab.iniciar_drenaje(invalid)


@pytest.mark.parametrize("invalid", [None, True, "x", "", "0" * 47, "g" * 48])
def test_tokens_invalidos_no_cambian_estado(lab, invalid):
    with pytest.raises(AdmisionRechazada):
        lab.iniciar_peticion(4, invalid)
    with pytest.raises(AdmisionRechazada):
        lab.cerrar_sesion(4, invalid)


def test_uso_simultaneo_16_clientes_y_drenaje_resultado_consistente(lab):
    start = Barrier(17)

    def join():
        start.wait()
        try:
            return lab.abrir_sesion(4)
        except AdmisionRechazada:
            return None

    def drain():
        start.wait()
        return lab.iniciar_drenaje(4)

    with ThreadPoolExecutor(max_workers=17) as pool:
        futures = [pool.submit(join) for _ in range(16)]
        ending = pool.submit(drain)
        tickets = [future.result() for future in futures]
        result = ending.result()

    admitted = [token for token in tickets if token is not None]
    assert len(admitted) == len(set(admitted))
    assert result["autoriza_borrado_fisico"] is False
    assert lab.observar(4)["sesiones_viewtv_pendientes"] == len(admitted)
    with pytest.raises(AdmisionRechazada):
        lab.abrir_sesion(4)
    for token in admitted:
        lab.cerrar_sesion(4, token)
    assert lab.observar(4)["estado"] == "listo_para_preflight"


def test_interrupcion_de_proceso_no_libera_fila_ni_desbloquea(lab):
    # Un segundo PROCESO abre una sesión y termina sin cerrarla.
    # La base privada sobrevive y debe detener el drenaje hasta
    # una reconciliación explícita del token.
    code = (
        "import sys;"
        "from pathlib import Path;"
        "from worker.retirement_playback_admission_0027 "
        "import LaboratorioAdmision0027;"
        "print(LaboratorioAdmision0027(Path(sys.argv[1])).abrir_sesion(4))"
    )
    child = subprocess.run(
        [sys.executable, "-c", code, str(lab.root)],
        capture_output=True, text=True, check=True, timeout=15,
    )
    token = child.stdout.strip()
    assert len(token) == 48
    lab2 = LaboratorioAdmision0027(lab.root)
    result = lab2.iniciar_drenaje(4)
    assert result["estado"] == "drenando"
    assert lab2.observar(4)["sesiones_viewtv_pendientes"] == 1
    assert result["autoriza_borrado_fisico"] is False
    # Solo el test conoce el token ficticio para cerrar la fila.
    lab2.cerrar_sesion(4, token)
    assert lab2.observar(4)["estado"] == "listo_para_preflight"


def test_un_medio_no_bloquea_sesiones_de_otro(lab):
    first = lab.abrir_sesion(4)
    assert lab.iniciar_drenaje(4)["estado"] == "drenando"
    other = lab.abrir_sesion(5)
    assert lab.observar(5)["estado"] == "libre"
    assert lab.observar(4)["estado"] == "drenando"
    lab.cerrar_sesion(5, other)
    lab.cerrar_sesion(4, first)


def test_proteccion_de_db_privada_rechaza_link_adicional(lab):
    alias = lab.root / "db-extra-link"
    os.link(lab.database, alias)
    try:
        with pytest.raises(AdmisionRechazada):
            lab.abrir_sesion(4)
    finally:
        alias.unlink()


def test_base_no_puede_reemplazarse_por_symlink(lab):
    backup = lab.root / "respaldo-privado"
    lab.database.rename(backup)
    lab.database.symlink_to(backup)
    try:
        with pytest.raises(AdmisionRechazada):
            lab.abrir_sesion(4)
    finally:
        lab.database.unlink()
        backup.rename(lab.database)


def test_no_se_puede_abrir_base_de_produccion(tmp_path):
    with pytest.raises(AdmisionRechazada):
        LaboratorioAdmision0027(tmp_path)


def test_estado_sql_invalido_falla_cerrado(lab):
    with sqlite3.connect(str(lab.database)) as conn:
        conn.execute("PRAGMA ignore_check_constraints=ON")
        conn.execute(
            "INSERT INTO peliculas(id,estado) VALUES (7,'invalido')"
        )
    with pytest.raises(AdmisionRechazada):
        lab.observar(7)


def test_no_existe_operacion_de_liberar_pelicula(lab):
    for name in ("borrar", "retirar", "desbloquear", "habilitar_borrado"):
        assert not hasattr(lab, name)
