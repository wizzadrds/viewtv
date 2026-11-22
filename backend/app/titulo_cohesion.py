"""Resolver la identidad TMDB y títulos equivalentes de una carátula.

No se confunde una búsqueda amplia de Jackett con una fuente verificada.
Las consultas cortas solo descubren candidatos, nunca los autorizan.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from app.tmdb import TMDBClient, TMDBError

EPISODE_CODE = re.compile(r"\s+S\d{1,3}E\d{1,3}\s*$", re.IGNORECASE)


def tokens(value: str) -> tuple[str, ...]:
    simple = "".join(
        letter for letter in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(letter)
    )
    simple = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", simple)
    return tuple(re.findall(r"[a-z0-9]+", simple))


def _base_title(title: str, kind: str) -> str:
    return EPISODE_CODE.sub("", title).strip() if kind == "serie" else title.strip()


def _candidate_year(record: dict, kind: str) -> int | None:
    raw = record.get("release_date" if kind == "pelicula" else "first_air_date")
    if isinstance(raw, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return int(raw[:4])
    return None


def _valid_title(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if (
        not 2 <= len(value) <= 250
        or any(ord(ch) < 32 for ch in value)
        or len(tokens(value)) == 0
    ):
        return None
    return value


def _extract_aliases(detail: dict, kind: str) -> tuple[str, ...]:
    seen: set[tuple[str, ...]] = set()
    values: list[str] = []

    def add(value: object) -> None:
        title = _valid_title(value)
        if title:
            tok = tokens(title)
            if tok not in seen and len(values) < 24:
                seen.add(tok)
                values.append(title)

    primary = "title" if kind == "pelicula" else "name"
    original = "original_title" if kind == "pelicula" else "original_name"
    add(detail.get(primary))
    add(detail.get(original))
    translated = detail.get("translations")
    if isinstance(translated, dict) and isinstance(translated.get("translations"), list):
        for row in translated["translations"][:100]:
            if not isinstance(row, dict) or row.get("iso_639_1") not in ("es", "en"):
                continue
            if isinstance(row.get("data"), dict):
                add(row["data"].get(primary))
    alternatives = detail.get("alternative_titles")
    if isinstance(alternatives, dict):
        raw = alternatives.get("titles" if kind == "pelicula" else "results")
        if isinstance(raw, list):
            for row in raw[:100]:
                if isinstance(row, dict) and row.get("iso_3166_1") in (
                    "ES", "US", "GB", "MX", "AR",
                ):
                    add(row.get("title"))
    return tuple(values)


@lru_cache(maxsize=512)
def aliases_para_solicitud(
    title: str,
    kind: str,
    year: int | None,
    tmdb_id: int | None = None,
) -> tuple[str, ...]:
    """Vincula un ID de carátula explícito o resuelve un ID único por título/año.

    Si hay dos fichas distintas igual de compatibles, no inventa alias.
    """
    if kind not in ("pelicula", "serie"):
        return ()
    query = _base_title(title, kind)
    if not _valid_title(query):
        return ()
    try:
        client = TMDBClient()
        identity: int | None = None
        if tmdb_id is not None:
            if type(tmdb_id) is not int or not 1 <= tmdb_id <= 2_147_483_647:
                return ()
            identity = tmdb_id
        else:
            matches = client.search(kind, query)
            valid: set[int] = set()
            fields = ("title", "original_title") if kind == "pelicula" else (
                "name", "original_name",
            )
            for item in matches[:40]:
                if not isinstance(item, dict) or item.get("adult") is True:
                    continue
                if tokens(query) not in [
                    tokens(item[f]) for f in fields if isinstance(item.get(f), str)
                ]:
                    continue
                found_year = _candidate_year(item, kind)
                if year is not None and (
                    found_year is None or abs(year - found_year) > 1
                ):
                    continue
                if type(item.get("id")) is int and 1 <= item["id"] <= 2_147_483_647:
                    valid.add(item["id"])
            if len(valid) != 1:
                return ()
            identity = valid.pop()

        detail = client.details_with_aliases(kind, identity)
        if detail.get("id") != identity or detail.get("adult") is True:
            return ()
        found_year = _candidate_year(detail, kind)
        if year is not None and found_year is not None and abs(year - found_year) > 1:
            return ()
        aliases = _extract_aliases(detail, kind)
        # Incluso si la ficha ha sido renombrada, el título registrado debe
        # corresponder a una variante oficial de esa misma identidad.
        if tmdb_id is None and tokens(query) not in {tokens(alias) for alias in aliases}:
            return ()
        return aliases
    except (TMDBError, ValueError, TypeError):
        return ()


def consultas_jackett(
    title: str, kind: str, year: int | None, aliases: tuple[str, ...],
) -> tuple[str, ...]:
    """Hasta 6 consultas: local/original con y sin año, alternativa y subtítulo.

    El subtítulo es únicamente un medio de descubrimiento: el filtro final
    exige coincidencia de identidad, año, tipo y episodio.
    """
    base = _base_title(title, kind)
    episode = title[len(base):].strip() if kind == "serie" else ""
    official = [base] + [v for v in aliases if _valid_title(v)]
    distinct: list[str] = []
    keys: set[tuple[str, ...]] = set()
    for value in official:
        key = tokens(value)
        if key and key not in keys:
            keys.add(key)
            distinct.append(value)

    first = distinct[0] if distinct else base
    other = distinct[1] if len(distinct) > 1 else None
    alternate = distinct[2] if len(distinct) > 2 else None

    short = None
    if aliases:
        for candidate in distinct:
            tail = re.split(r"\s*[:–—]\s*", candidate)[-1].strip()
            if tail != candidate and len(tokens(tail)) >= 1 and len(tail) >= 5:
                short = tail
                break

    queries: list[str] = []
    seen: set[tuple[str, ...]] = set()

    def add(value: str | None, *, with_year: bool) -> None:
        if value is None or len(queries) >= 6:
            return
        phrase = " ".join((value + (" " + episode if episode else "")).split())
        if with_year and year and not episode:
            phrase += f" {year}"
        key = tokens(phrase)
        if not key or key in seen or len(phrase) > 200:
            return
        seen.add(key)
        queries.append(phrase)

    add(first, with_year=True)
    add(other, with_year=True)
    if year and not episode:
        add(first, with_year=False)
        add(other, with_year=False)
    add(alternate, with_year=True)
    add(short, with_year=False)
    # En series sin año hay presupuesto para otra variante oficial.
    if not year and len(distinct) > 3:
        add(distinct[3], with_year=False)
    return tuple(queries)


@lru_cache(maxsize=512)
def solicitud_sin_anio_ambigua(title: str, kind: str) -> bool:
    """No ofrecer fuentes si TMDB conoce varios filmes con ese mismo nombre.

    Solo se aplica a solicitudes manuales sin año ni ID de carátula.
    Ante fallo de TMDB, el filtro textual conservador sigue vigente.
    """
    if kind != "pelicula" or not _valid_title(title):
        return False
    try:
        candidates = TMDBClient().search(kind, title)
    except (TMDBError, ValueError, TypeError):
        return False
    ids: set[int] = set()
    for entry in candidates[:40]:
        if not isinstance(entry, dict) or entry.get("adult") is True:
            continue
        if tokens(title) not in (
            tokens(entry.get("title", "")),
            tokens(entry.get("original_title", "")),
        ):
            continue
        identity = entry.get("id")
        if type(identity) is int and 1 <= identity <= 2_147_483_647:
            ids.add(identity)
    return len(ids) > 1
