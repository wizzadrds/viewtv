"""Regresiones para demostrar que un torrent ajeno/activo no se retira."""
from datetime import UTC, datetime

import pytest
from worker.retirement_guards import comprobar_torrent_para_retirada

from app.models import Descarga

HASH = "a" * 40


def propia() -> Descarga:
    return Descarga(
        id=4,
        solicitud_id=10,
        titulo="Película ficticia",
        info_hash=HASH,
        qbittorrent_hash=HASH,
        estado="completada",
        estado_verificacion="verificada",
        verificada_en=datetime.now(UTC),
        progreso=1,
        organizacion_estado="organizada",
    )


def torrent() -> dict:
    return {
        "hash": HASH,
        "tags": "viewtv-descarga-4",
        "save_path": r"C:\VIEWTV\media\descargas_temporales",
        "state": "stoppedUP",
        "progress": 1,
    }


def test_solo_torrent_propio_detenido_supera_guardia_parcial():
    assert comprobar_torrent_para_retirada(propia(), [torrent()]) == "apto_parcialmente"
    assert comprobar_torrent_para_retirada(propia(), [
        {**torrent(), "state": "pausedUP"},
    ]) == "apto_parcialmente"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"hash": "b" * 40}, "identidad_incorrecta"),
        ({"tags": ""}, "propiedad_no_acreditada"),
        ({"tags": "viewtv-descarga-5"}, "propiedad_no_acreditada"),
        ({"tags": "viewtv-descarga-4,viewtv-descarga-5"}, "propiedad_no_acreditada"),
        ({"tags": "viewtv-descarga-4,viewtv-descarga-4"}, "propiedad_no_acreditada"),
        ({"save_path": r"C:\Otros"}, "carpeta_no_autorizada"),
        ({"state": "uploading"}, "torrent_en_uso_o_estado_desconocido"),
        ({"state": "stalledUP"}, "torrent_en_uso_o_estado_desconocido"),
        ({"state": "checkingUP"}, "torrent_en_uso_o_estado_desconocido"),
        ({"state": "missingFiles"}, "torrent_en_uso_o_estado_desconocido"),
        ({"state": "desconocido"}, "torrent_en_uso_o_estado_desconocido"),
        ({"progress": 0.99}, "torrent_no_completado"),
    ],
)
def test_rechazo_por_torrent_inseguro(change, reason):
    assert comprobar_torrent_para_retirada(
        propia(), [{**torrent(), **change}],
    ) == reason


def test_rechazo_sin_torrent_y_duplicado():
    assert comprobar_torrent_para_retirada(propia(), []) == "torrent_ausente_o_ambiguo"
    assert comprobar_torrent_para_retirada(propia(), [
        torrent(), torrent(),
    ]) == "torrent_ausente_o_ambiguo"


@pytest.mark.parametrize("field,value", [
    ("organizacion_estado", "pendiente"),
    ("estado", "descargando"),
    ("estado_verificacion", "pendiente"),
    ("progreso", 0.5),
    ("qbittorrent_hash", None),
    ("verificada_en", None),
])
def test_rechazo_de_registro_no_organizado(field, value):
    record = propia()
    setattr(record, field, value)
    assert comprobar_torrent_para_retirada(
        record, [torrent()],
    ) == "registro_no_verificado"
