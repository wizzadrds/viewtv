"""Catálogo de FICHAS TMDB: SQLite separada, sin ficheros multimedia.

La API la abre exclusivamente en modo lectura. El catalogador dedicado es
el único escritor, en un volumen Docker distinto del SQLite de ViewTV y
sin acceso a /media. Las fotos se sirven desde CDN TMDB por URL validada;
jamás guardamos vídeos, imágenes ni claves API en esta base.
"""
import json
import os
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.tmdb import TMDBClient

IMAGE_RE = re.compile(r"/[A-Za-z0-9_-]{1,128}\.(?:jpg|jpeg|png|webp)\Z")
MAX_TMDB_ID = 2_147_483_647
PAGE_SIZE = 20
MAX_CACHE_DAYS = 150  # Por debajo de 6 meses: caducidad de metadatos TMDB.


def _catalog_limit(raw: str) -> int:
    """Límite configurable por entorno; no permitir crecimiento sin presupuesto."""
    if not raw.isdecimal() or not 20_000 <= int(raw) <= 1_000_000:
        raise ValueError("VIEWTV_CATALOG_MAX_ITEMS debe estar entre 20000 y 1000000.")
    return int(raw)


MAX_CATALOG = _catalog_limit(os.getenv("VIEWTV_CATALOG_MAX_ITEMS", "250000"))
MAX_PAGE = 50_000


def _expiry_cutoff(now: datetime | None = None) -> str:
    """Fechas SQLite UTC comparables sin ambigüedad de zona horaria."""
    instant = now or datetime.now(UTC)
    return (instant - timedelta(days=MAX_CACHE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")


def prune_expired(db: sqlite3.Connection, *, now: datetime | None = None) -> int:
    """Borra SOLO fichas TMDB caducadas; nunca películas ni descargas."""
    result = db.execute(
        "DELETE FROM ficha WHERE actualizado_en < ?", (_expiry_cutoff(now),)
    )
    return result.rowcount


def catalog_path() -> Path:
    return Path(os.getenv("VIEWTV_CATALOG_PATH", "/catalogo/metadatos.db"))


def open_reader() -> sqlite3.Connection | None:
    path = catalog_path()
    if not path.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=3)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA busy_timeout=3000")
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            db.close()
            return None
        return db
    except sqlite3.Error:
        return None


def create_writer(path: Path | None = None) -> sqlite3.Connection:
    """Solo catalogador: crea esquema de base nueva, nunca modifica viewtv.db."""
    target = path or catalog_path()
    if target.name != "metadatos.db":
        raise ValueError("Nombre de base de catálogo no autorizado.")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(target, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=5000")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, 1):
        db.close()
        raise RuntimeError("Versión desconocida de catálogo.")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS ficha (
          tipo TEXT NOT NULL CHECK(tipo IN ('pelicula','serie')),
          tmdb_id INTEGER NOT NULL CHECK(tmdb_id BETWEEN 1 AND 2147483647),
          titulo TEXT NOT NULL,
          sinopsis TEXT,
          anio INTEGER,
          imagen_portada TEXT,
          imagen_fondo TEXT,
          generos_ids TEXT NOT NULL DEFAULT '[]',
          popularidad REAL NOT NULL DEFAULT 0,
          actualizado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (tipo, tmdb_id)
        );
        CREATE INDEX IF NOT EXISTS idx_ficha_tipo_popularidad
          ON ficha(tipo, popularidad DESC);
        CREATE INDEX IF NOT EXISTS idx_ficha_anio ON ficha(tipo, anio);
        CREATE INDEX IF NOT EXISTS idx_ficha_actualizado_en ON ficha(actualizado_en);
        CREATE TABLE IF NOT EXISTS cursor_ingesta (
          clave TEXT PRIMARY KEY,
          pagina_siguiente INTEGER NOT NULL DEFAULT 1,
          actualizado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS estado_ingesta (
          clave TEXT PRIMARY KEY,
          valor TEXT NOT NULL
        );
        PRAGMA user_version=1;
        """
    )
    return db


def _path(value: object) -> str | None:
    return value if isinstance(value, str) and IMAGE_RE.fullmatch(value) else None


def normalize_entry(data: dict, kind: str) -> dict | None:
    """Importa la respuesta oficial de TMDB; no confía en HTML ni torrents."""
    if kind not in ("pelicula", "serie") or data.get("adult") is True:
        return None
    identifier = data.get("id")
    title = data.get("title" if kind == "pelicula" else "name")
    if (type(identifier) is not int or not 1 <= identifier <= MAX_TMDB_ID
        or not isinstance(title, str) or not 1 <= len(title.strip()) <= 500
        or any(ord(c) < 32 for c in title)):
        return None
    date = data.get("release_date" if kind == "pelicula" else "first_air_date")
    year = None
    if isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        year = int(date[:4])
        if not 1870 <= year <= datetime.now(UTC).year:
            year = None
    genres = data.get("genre_ids")
    ids = sorted({
        g for g in genres if type(g) is int and 1 <= g <= 99999
    })[:30] if isinstance(genres, list) else []
    overview = data.get("overview")
    popularity = data.get("popularity")
    popularity = float(popularity) if type(popularity) in (float, int) else 0.0
    if not 0 <= popularity <= 1_000_000_000:
        popularity = 0.0
    return {
        "tipo": kind, "tmdb_id": identifier, "titulo": title.strip(),
        "sinopsis": overview[:8000] if isinstance(overview, str) else None,
        "anio": year, "imagen_portada": _path(data.get("poster_path")),
        "imagen_fondo": _path(data.get("backdrop_path")),
        "generos_ids": json.dumps(ids, separators=(",", ":")),
        "popularidad": popularity,
    }


def upsert_page(db: sqlite3.Connection, kind: str, raw: dict) -> int:
    results = raw.get("results")
    if not isinstance(results, list):
        raise ValueError("TMDB devolvió resultados no válidos.")
    if len(results) > 20:
        raise ValueError("TMDB devolvió más de 20 fichas en una página.")
    values = [item for row in results
              if isinstance(row, dict)
              if (item := normalize_entry(row, kind)) is not None]
    # Límite duro de fichas únicas: las existentes se actualizan,
    # y las nuevas solo entran si queda capacidad.
    current_count = db.execute("SELECT COUNT(*) FROM ficha").fetchone()[0]
    free = max(0, MAX_CATALOG - current_count)
    if values:
        kind_ids = values[0]["tipo"]
        ids = [item["tmdb_id"] for item in values]
        placeholders = ",".join("?" for _ in ids)
        known = {
            row[0] for row in db.execute(
                "SELECT tmdb_id FROM ficha WHERE tipo=? AND tmdb_id IN ("
                + placeholders + ")", [kind_ids, *ids],
            ).fetchall()
        }
        limited = []
        for item in values:
            if item["tmdb_id"] in known:
                limited.append(item)
            elif free:
                limited.append(item)
                free -= 1
        values = limited
    db.executemany(
        """
        INSERT INTO ficha
          (tipo,tmdb_id,titulo,sinopsis,anio,imagen_portada,imagen_fondo,
           generos_ids,popularidad)
        VALUES (:tipo,:tmdb_id,:titulo,:sinopsis,:anio,:imagen_portada,:imagen_fondo,
                :generos_ids,:popularidad)
        ON CONFLICT (tipo,tmdb_id) DO UPDATE SET
          titulo=excluded.titulo, sinopsis=excluded.sinopsis,
          anio=excluded.anio, imagen_portada=excluded.imagen_portada,
          imagen_fondo=excluded.imagen_fondo, generos_ids=excluded.generos_ids,
          popularidad=excluded.popularidad, actualizado_en=CURRENT_TIMESTAMP
        """,
        values,
    )
    return len(values)


def _format_row(row: sqlite3.Row) -> dict:
    portrait = row["imagen_portada"]
    backdrop = row["imagen_fondo"]
    return {
        "tmdb_id": row["tmdb_id"],
        "tipo": row["tipo"],
        "titulo": row["titulo"],
        "sinopsis": row["sinopsis"],
        "anio": row["anio"],
        "imagen_portada": TMDBClient.image_url(portrait, "w500") if portrait else None,
        "imagen_fondo": TMDBClient.image_url(backdrop, "w1280") if backdrop else None,
    }


def _query(
    *,
    kind: str | None = None,
    year: int | None = None,
    genre: int | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = PAGE_SIZE,
) -> dict | None:
    """Devuelve None si la BD no existe, sin escribirla desde la API."""
    if not 1 <= page <= MAX_PAGE or not 1 <= limit <= 50:
        raise ValueError("Paginación no válida.")
    db = open_reader()
    if db is None:
        return None
    try:
        where = ["f.actualizado_en >= ?"]
        args: list[object] = [_expiry_cutoff()]
        if kind:
            if kind not in ("pelicula", "serie"):
                raise ValueError("Tipo inválido.")
            where.append("f.tipo = ?")
            args.append(kind)
        if year:
            where.append("f.anio = ?")
            args.append(year)
        if genre:
            where.append(
                "EXISTS (SELECT 1 FROM json_each(f.generos_ids) AS j "
                "WHERE j.value = ?)"
            )
            args.append(genre)
        if search:
            if not 2 <= len(search.strip()) <= 100:
                raise ValueError("Búsqueda no válida.")
            # Escapar % y _ para que el navegador no envíe patrones SQL.
            term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where.append("f.titulo LIKE ? ESCAPE '\\' COLLATE NOCASE")
            args.append("%" + term + "%")
        query = " AND ".join(where)
        total = db.execute(
            "SELECT COUNT(*) FROM ficha AS f WHERE " + query, args,
        ).fetchone()[0]
        rows = db.execute(
            "SELECT f.* FROM ficha AS f WHERE " + query
            + " ORDER BY f.popularidad DESC, f.tmdb_id DESC LIMIT ? OFFSET ?",
            [*args, limit, (page - 1) * limit],
        ).fetchall()
        return {
            "elementos": [_format_row(r) for r in rows],
            "total": total,
            "pagina": page,
            "paginas": (total + limit - 1) // limit,
            "fuente": "catalogo_local",
        }
    except sqlite3.Error:
        return None
    finally:
        db.close()


def read_shelf(kind: str, *, genre: int | None = None,
               year: int | None = None, page: int = 1) -> dict | None:
    return _query(kind=kind, year=year, genre=genre, page=page)


def search_shelf(kind: str, title: str, *, page: int = 1) -> dict | None:
    return _query(kind=kind, search=title, page=page)


def status() -> dict:
    db = open_reader()
    if db is None:
        return {"total": 0, "peliculas": 0, "series": 0, "ultima_actualizacion": None}
    try:
        counts = dict(db.execute(
            "SELECT tipo, COUNT(*) FROM ficha WHERE actualizado_en >= ? GROUP BY tipo",
            (_expiry_cutoff(),),
        ).fetchall())
        recent = db.execute(
            "SELECT valor FROM estado_ingesta WHERE clave='ultima_actualizacion'"
        ).fetchone()
        return {
            "total": sum(counts.values()),
            "peliculas": counts.get("pelicula", 0),
            "series": counts.get("serie", 0),
            "ultima_actualizacion": recent[0] if recent else None,
        }
    except sqlite3.Error:
        return {"total": 0, "peliculas": 0, "series": 0, "ultima_actualizacion": None}
    finally:
        db.close()
