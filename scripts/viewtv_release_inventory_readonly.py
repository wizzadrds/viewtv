"""Inventario agregado y sin datos personales para verificar la salida de VIEWTV.

Se ejecuta en un contenedor efímero SIN red con el volumen /data en
solo lectura. Nunca imprime títulos, perfiles, URL, hashes ni errores sin filtrar.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter

DATABASE_URI = "file:/data/viewtv.db?mode=ro"


def classify_failure(message: str | None) -> str:
    """Clasifica un error sin revelar texto de producción."""
    if not message:
        return "sin_detalle"
    normalized = message.casefold()
    if "jackett" in normalized or "indexador" in normalized:
        if "configurad" in normalized and (
            "no est" in normalized or "sin " in normalized
        ):
            return "proveedor_busqueda_sin_configuracion"
        if "comunicaci" in normalized or "conexi" in normalized:
            return "proveedor_busqueda_sin_conexion"
        if "xml" in normalized or "respuesta" in normalized:
            return "proveedor_busqueda_respuesta"
        return "proveedor_busqueda_otro"
    if "qbittorrent" in normalized or "torrent" in normalized:
        return "gestor_descargas"
    if "tmdb" in normalized:
        return "metadatos"
    if "timeout" in normalized or "temporiz" in normalized:
        return "tiempo_espera"
    if "resultado" in normalized and "no " in normalized:
        return "resultado_no_disponible"
    if "http" in normalized or "conexi" in normalized:
        return "conexion"
    return "otro_error_sin_detalle"


def summarize(conn: sqlite3.Connection) -> dict[str, object]:
    """Solo agregados. No devuelve registros de usuario."""
    counts = {}
    for name in ("perfil", "medio", "solicitud", "resultado_busqueda", "descarga"):
        counts[name] = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]

    active_profiles = conn.execute(
        "SELECT COUNT(*) FROM perfil WHERE activo = 1"
    ).fetchone()[0]
    available_media = conn.execute(
        "SELECT COUNT(*) FROM medio WHERE disponible_en_jellyfin = 1"
    ).fetchone()[0]
    request_states = dict(
        conn.execute("SELECT estado, COUNT(*) FROM solicitud GROUP BY estado")
    )
    download_states = dict(
        conn.execute("SELECT estado, COUNT(*) FROM descarga GROUP BY estado")
    )
    start_states = dict(
        conn.execute(
            "SELECT inicio_estado, COUNT(*) FROM descarga GROUP BY inicio_estado"
        )
    )
    failed = conn.execute(
        "SELECT intentos, max_intentos, ultimo_error "
        "FROM solicitud WHERE estado = 'fallida'"
    ).fetchall()
    failure_causes = Counter(classify_failure(item[2]) for item in failed)
    exhausted = sum(item[0] >= item[1] for item in failed)

    return {
        "tablas_conteo": counts,
        "perfiles_activos": active_profiles,
        "medios_disponibles_en_jellyfin": available_media,
        "solicitudes_por_estado": request_states,
        "descargas_por_estado": download_states,
        "inicio_descargas_por_estado": start_states,
        "fallos_clasificados_sin_texto": dict(sorted(failure_causes.items())),
        "solicitudes_fallidas_sin_intentos": exhausted,
    }


def main() -> None:
    with sqlite3.connect(DATABASE_URI, uri=True, timeout=10) as conn:
        conn.execute("PRAGMA query_only = ON")
        report = summarize(conn)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
