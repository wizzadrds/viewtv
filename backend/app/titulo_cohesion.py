"""Variantes oficiales de títulos TMDB para conectar carátulas y búsquedas.

La solicitud se mantiene en su idioma original. Solo se añaden traducciones
si una búsqueda TMDB encuentra una identidad inequívoca por título y año.
No se guardan URLs/torrents ni se dan coincidencias por una palabra aislada.
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
    if (not 2 <= len(value) <= 250
        or any(ord(ch) < 32 for ch in value)
        or len(tokens(value)) == 0):
        return None
    return value


def _extract_aliases(detail: dict, kind: str) -> tuple[str, ...]:
    seen: set[tuple[str, ...]] = set()
    values: list[str] = []
    def add(value: object) -> None:
        title = _valid_title(value)
        if title:
            tok = tokens(title)
            if tok not in seen and len(values) < 20:
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
def aliases_para_solicitud(title: str, kind: str, year: int | None) -> tuple[str, ...]:
    """Verifica unívocamente la ficha mediante títulos y año, sin inventar IDs."""
    if kind not in ("pelicula", "serie"):
        return ()
    query = _base_title(title, kind)
    if not _valid_title(query):
        return ()
    try:
        client = TMDBClient()
        matches = client.search(kind, query)
        valid = []
        for item in matches[:20]:
            if not isinstance(item, dict):
                continue
            fields = ("title", "original_title") if kind == "pelicula" else (
                "name", "original_name",
            )
            if tokens(query) not in [tokens(item.get(f, "")) for f in fields
                                     if isinstance(item.get(f), str)]:
                continue
            candidate_year = _candidate_year(item, kind)
            if year is not None and candidate_year is not None and year != candidate_year:
                continue
            if type(item.get("id")) is int and 1 <= item["id"] <= 2_147_483_647:
                valid.append(item["id"])
        unique = set(valid)
        if len(unique) != 1:
            return ()
        identity = unique.pop()
        detail = client.details_with_aliases(kind, identity)
        if detail.get("id") != identity or detail.get("adult") is True:
            return ()
        return _extract_aliases(detail, kind)
    except (TMDBError, ValueError, TypeError):
        # Sin TMDB: se conserva la búsqueda original, nunca inventar alias.
        return ()


def consultas_jackett(
    title: str, kind: str, year: int | None, aliases: tuple[str, ...],
) -> tuple[str, ...]:
    """Máximo cuatro consultas por solicitud, deduplicadas y sin URLs arbitrarias."""
    base = _base_title(title, kind)
    episode = title[len(base):].strip() if kind == "serie" else ""
    options = [base]
    options.extend(aliases[:12])
    # Reservar una consulta para el subtítulo breve cuando una franquicia
    # tiene muchos títulos traducidos, sin relajar jamás la coincidencia final.
    tail_query = None
    if aliases:
        for candidate in options:
            tail = re.split(r"\s*[:–—-]\s*", candidate)[-1].strip()
            if tail != candidate and len(tail) >= 5:
                tail_query = tail
                break
    first_budget = 3 if tail_query else 4
    queries = []
    seen = set()
    def add(value: str, *, include_year: bool = True, max_queries: int = 4) -> None:
        if len(queries) >= max_queries:
            return
        phrase = value + (" " + episode if episode else "")
        phrase = " ".join(phrase.split())
        key = tokens(phrase)
        if not key or key in seen or len(phrase) > 200:
            return
        seen.add(key)
        queries.append(
            phrase + (f" {year}" if year and not episode and include_year else "")
        )

    for option in options:
        add(option, max_queries=first_budget)
    # Se busca «Doomsday» ampliamente, pero el filtro de resultados exige
    # «Vengadores: Doomsday» o su título oficial «Avengers: Doomsday».
    if tail_query is not None:
        add(tail_query, include_year=False)
    return tuple(queries)
