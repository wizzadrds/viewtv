"""Importador gradual TMDB: SOLO metadatos, sin conexión con qBit/Jellyfin.

Servicio Docker dedicado con volumen de catálogo propio, sin /media,
ni acceso al SQLite viewtv.db. Se bloquea para evitar dobles importadores.
Una iteración lee como máximo 96 páginas (~1.920 fichas) cada seis horas,
respeta errores/rate limits TMDB y conserva el progreso por cada fuente.
"""
import fcntl
import sys
import time
from datetime import UTC, datetime

from app.catalogo_cache import catalog_path, create_writer, prune_expired, upsert_page
from app.tmdb import TMDBClient, TMDBError

INTERVAL_SECONDS = 6 * 60 * 60
PAGES_PER_STREAM = 3
MAX_REQUESTS_PER_CYCLE = 96
REQUEST_PAUSE_SECONDS = 0.65


def _streams() -> list[tuple[str, str, int | None, int | None]]:
    year = datetime.now(UTC).year
    years = sorted({
        1950, 1960, 1970, 1980, 1990, 2000, 2005, 2010,
        2015, 2018, 2020, 2021, 2022, 2023, year - 2, year - 1, year,
    })
    streams = [
        ("peliculas", "pelicula", None, None),
        ("series", "serie", None, None),
        ("accion", "pelicula", 28, None),
        ("terror", "pelicula", 27, None),
        ("comedia", "pelicula", 35, None),
        ("ciencia-ficcion", "pelicula", 878, None),
        ("series-misterio", "serie", 9648, None),
        ("series-drama", "serie", 18, None),
        ("series-comedia", "serie", 35, None),
        ("series-crimen", "serie", 80, None),
        ("peliculas-drama", "pelicula", 18, None),
        ("peliculas-animacion", "pelicula", 16, None),
    ]
    streams += [(f"peliculas-{y}", "pelicula", None, y)
                for y in years if 1900 <= y <= year]
    return streams


def _read_marker(db, key: str) -> str | None:
    row = db.execute("SELECT valor FROM estado_ingesta WHERE clave=?", (key,)).fetchone()
    return row[0] if row else None


def _write_marker(db, key: str, value: str) -> None:
    db.execute(
        "INSERT INTO estado_ingesta(clave,valor) VALUES (?,?) "
        "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (key, value),
    )


def refresh(*, now: datetime | None = None, pause: float = REQUEST_PAUSE_SECONDS,
            pages_per_stream: int = PAGES_PER_STREAM, client=None) -> dict:
    """Una pasada segura. Sin commit a BD principal; todo es reversible."""
    if not 0 <= pause <= 10 or not 1 <= pages_per_stream <= 10:
        raise ValueError("Presupuesto de consulta no válido.")
    now = now or datetime.now(UTC)
    path = catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Lock file dura toda la pasada. El mismo servicio puede reiniciarse
    # sin ejecutar el programa dos veces simultáneamente.
    with (path.parent / ".catalogador.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"estado": "otro_catalogador_activo"}
        db = create_writer(path)
        requests = 0
        valid_entries = 0
        try:
            # La caducidad no depende de completar la consulta a TMDB.
            deleted = prune_expired(db, now=now)
            db.commit()
            if deleted:
                print("FICHAS_CADUCADAS_DEPURADAS=" + str(deleted), flush=True)
            last = _read_marker(db, "ultima_ejecucion")
            if last is not None:
                last_time = datetime.fromisoformat(last)
                if now.timestamp() - last_time.timestamp() < INTERVAL_SECONDS:
                    return {"estado": "esperando_proximo_ciclo", "peticiones": 0}
            _write_marker(db, "ultima_ejecucion", now.isoformat())
            db.commit()
            source = client or TMDBClient()
            for key, kind, genre, year in _streams():
                # Al alcanzar la cuota se siguen renovando fichas existentes.
                if requests >= MAX_REQUESTS_PER_CYCLE:
                    break
                stored = db.execute(
                    "SELECT pagina_siguiente FROM cursor_ingesta WHERE clave=?", (key,),
                ).fetchone()
                page = stored[0] if stored else 1
                for _ in range(pages_per_stream):
                    if requests >= MAX_REQUESTS_PER_CYCLE:
                        break
                    try:
                        response = source.discover(
                            kind, genre_id=genre, release_year=year, page=page,
                        )
                        requests += 1
                        saved = upsert_page(db, kind, response)
                        valid_entries += saved
                        total_pages = response.get("total_pages", 500)
                        if type(total_pages) is not int or total_pages < 1:
                            total_pages = 500
                        page = page + 1 if page < min(total_pages, 500) else 1
                        db.execute(
                            "INSERT INTO cursor_ingesta(clave,pagina_siguiente) "
                            "VALUES (?,?) ON CONFLICT(clave) DO UPDATE SET "
                            "pagina_siguiente=excluded.pagina_siguiente, "
                            "actualizado_en=CURRENT_TIMESTAMP", (key, page),
                        )
                        _write_marker(db, "ultima_actualizacion", datetime.now(UTC).isoformat())
                        db.commit()
                        if pause:
                            time.sleep(pause)
                    except (TMDBError, ValueError) as error:
                        # No imprimir URL, parámetros, título ni clave; abortar
                        # toda la pasada ante 429, caída de red o datos inválidos.
                        db.rollback()
                        print("CATALOGO_PROVEEDOR_NO_DISPONIBLE", flush=True)
                        return {
                            "estado": "parcial", "peticiones": requests,
                            "fichas_procesadas": valid_entries,
                            "error_tipo": type(error).__name__,
                        }
            total = db.execute("SELECT COUNT(*) FROM ficha").fetchone()[0]
            return {
                "estado": "correcto",
                "peticiones": requests,
                "fichas_procesadas": valid_entries,
                "fichas_unicas": total,
            }
        finally:
            db.close()


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "loop"
    if mode not in ("loop", "once"):
        raise SystemExit("Modo no permitido.")
    while True:
        try:
            result = refresh()
            print(
                "CATALOGADOR_ESTADO=" + str(result["estado"])
                + " PETICIONES=" + str(result.get("peticiones", 0))
                + " FICHAS_UNICAS=" + str(result.get("fichas_unicas", "no_calculado")),
                flush=True,
            )
        except (OSError, RuntimeError, TMDBError, ValueError) as error:
            # La clave/URLs nunca se imprimen en logs.
            print("CATALOGADOR_ERROR=" + type(error).__name__, flush=True)
            if mode == "once":
                raise SystemExit(1) from None
        if mode == "once":
            break
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
