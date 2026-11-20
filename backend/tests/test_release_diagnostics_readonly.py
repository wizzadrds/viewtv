"""Contratos de seguridad de los diagnósticos de salida rápida de VIEWTV."""

import importlib.util
import json
import sqlite3
from pathlib import Path

from app.jackett import JackettError


def _load_script(name: str):
    path = Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


categorize = _load_script("viewtv_jackett_probe_readonly").categorize
_inventory = _load_script("viewtv_release_inventory_readonly")
classify_failure, summarize = _inventory.classify_failure, _inventory.summarize


def _db_fixture() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.executescript(
        """
        CREATE TABLE perfil (activo INTEGER);
        CREATE TABLE medio (disponible_en_jellyfin INTEGER);
        CREATE TABLE solicitud (
            estado TEXT, intentos INTEGER, max_intentos INTEGER, ultimo_error TEXT
        );
        CREATE TABLE resultado_busqueda (id INTEGER);
        CREATE TABLE descarga (estado TEXT, inicio_estado TEXT);
        INSERT INTO perfil VALUES (1), (1), (0);
        INSERT INTO medio VALUES (1), (0);
        INSERT INTO solicitud VALUES
            ('fallida', 5, 5, 'Jackett Error de comunicación con CLAVE PRIVADA'),
            ('pendiente', 0, 5, NULL);
        INSERT INTO descarga VALUES ('seleccionada', 'pendiente');
        """
    )
    return db


def test_inventario_resumido_y_sin_datos_personales():
    with _db_fixture() as db:
        output = summarize(db)
    assert output["perfiles_activos"] == 2
    assert output["medios_disponibles_en_jellyfin"] == 1
    assert output["solicitudes_por_estado"] == {"fallida": 1, "pendiente": 1}
    assert output["descargas_por_estado"] == {"seleccionada": 1}
    assert output["solicitudes_fallidas_sin_intentos"] == 1
    serialized = json.dumps(output)
    assert "CLAVE PRIVADA" not in serialized
    assert "Jackett Error" not in serialized


def test_error_jackett_no_configurado_no_fuga():
    assert (
        classify_failure("Jackett no está configurado: token oculto")
        == "proveedor_busqueda_sin_configuracion"
    )


def test_error_jackett_conexion_no_fuga():
    assert (
        classify_failure("Error de comunicación con Jackett: url privada")
        == "proveedor_busqueda_sin_conexion"
    )


def test_error_jackett_xml_y_error_desconocido():
    assert classify_failure("Jackett devolvió una respuesta XML no válida") == (
        "proveedor_busqueda_respuesta"
    )
    assert classify_failure("dato secreto") == "otro_error_sin_detalle"


def test_error_jackett_probe_no_incluye_cadena():
    assert categorize(JackettError("falló conexión token secreto")) == ("jackett_no_disponible")
    assert categorize(RuntimeError("token secreto")) == "excepcion_no_prevista"
