"""Emparejamiento conservador de carátula TMDB y título publicado en Jackett.

No se aceptan fuentes por una palabra suelta de una franquicia, ni se
supone que el contenido del torrent coincida con la descripción.
"""
from __future__ import annotations

import math
import re
import unicodedata

_EPISODIO = re.compile(
    r"(?<![A-Z0-9])(?:S\d{1,3}[. _-]*E\d{1,3}|S\d{1,3}|\d{1,2}X\d{1,3})(?![A-Z0-9])",
    re.IGNORECASE,
)
_EPISODIO_CONCRETO = re.compile(
    r"(?<![A-Z0-9])S(?P<season>\d{1,3})[. _-]*E(?P<episode>\d{1,3})(?![A-Z0-9])",
    re.IGNORECASE,
)
_ARTICULOS_INICIALES = {
    "el", "la", "los", "las", "lo", "un", "una", "unos", "unas",
    "the", "a", "an", "le", "les", "der", "die", "das",
}
_CONECTORES = {
    "de", "del", "da", "do", "of", "and", "y", "en", "in", "the",
    "la", "el", "los", "las", "a", "an", "for", "por", "para", "con",
    "with", "to", "et", "e",
}
_ETIQUETAS = {
    "4k", "8k", "1080", "1080p", "2160", "2160p",
    "720", "720p", "480", "480p", "576", "576p", "web", "webrip",
    "webdl", "bluray", "bdrip", "brrip", "hdrip", "hdtv", "dvdrip",
    "remux", "hd", "uhd", "hdr", "hdr10", "dovi", "x264", "x265",
    "h264", "h265", "hevc", "av1", "aac", "ac3", "dts", "ddp",
    "dolby", "atmos", "multi", "dual", "vose", "spanish", "espanol",
    "castellano", "latino", "sub", "subs", "nf", "amzn", "hmax",
    "dsnp", "imax", "extended", "proper", "repack", "uncut",
    "complete", "director", "edition", "final", "esp", "eng",
    "es", "en", "audio", "hdr10plus", "xvid", "dubbed", "dub",
    "subbed", "truehd", "atmos", "dv", "h264", "h265", "r5",
    "dl", "rip", "ray", "p", "ac", "dd", "plus",
}
_RECHAZADOS = {
    "trailer", "teaser", "cam", "telesync", "extras",
}


def _tokens(value: str) -> list[str]:
    plain = "".join(
        letter for letter in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(letter)
    )
    plain = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", plain)
    pieces = re.findall(r"[a-z0-9]+", plain)
    words: list[str] = []
    i = 0
    while i < len(pieces):
        # Recuperar etiquetas "4k", "1080p", "h265" antes de comprobar
        # palabras significativas; conservar números de secuelas.
        if i + 1 < len(pieces) and pieces[i] + pieces[i + 1] in _ETIQUETAS:
            words.append(pieces[i] + pieces[i + 1])
            i += 2
        else:
            words.append(pieces[i])
            i += 1
    return words


def _nombre_significativo(value: str, *, torrent: bool) -> set[str]:
    words = _tokens(value)
    while words and words[0] in _ARTICULOS_INICIALES:
        words.pop(0)
    return {
        word for word in words
        if word not in _CONECTORES
        and not (torrent and (word in _ETIQUETAS or
                             (word.isdecimal() and 1870 <= int(word) <= 2200)))
    }


def _episodio_compatible(request: str, offered: str, kind: str) -> bool:
    if kind == "pelicula":
        return _EPISODIO.search(offered) is None
    if kind != "serie":
        return False
    requested = list(_EPISODIO_CONCRETO.finditer(request))
    if not requested:
        # Solicitudes históricas de series sin episodio concreto.
        return True
    found = list(_EPISODIO_CONCRETO.finditer(offered))
    if len(requested) != 1 or len(found) != 1:
        return False
    if (
        int(requested[0]["season"]) != int(found[0]["season"])
        or int(requested[0]["episode"]) != int(found[0]["episode"])
    ):
        return False
    # "S01E02E03" o "S01E02-S01E03" no equivalen a un capítulo individual.
    remainder = _EPISODIO_CONCRETO.sub("", offered)
    if re.search(r"(?<![A-Z0-9])E\d{1,3}(?![A-Z0-9])", remainder, re.I):
        return False
    return _EPISODIO.search(remainder) is None


def coincide_con_solicitud(
    titulo_solicitado: str,
    tipo_medio: str,
    anio: int | None,
    titulo_resultado: str,
    aliases: tuple[str, ...] = (),
) -> bool:
    """Valida nombres equivalentes por conjuntos de tokens, tipo y año.

    Con dos tokens significativos se requieren ambos; con tres se aceptan
    dos; con cuatro o más al menos un 75 %, sin palabras significativas
    ajenas a la ficha. El año explícito debe estar a ±1; sin año
    verificable se rechaza si la ficha dispone de año.
    """
    if not titulo_solicitado.strip() or not titulo_resultado.strip():
        return False
    if not _episodio_compatible(titulo_solicitado, titulo_resultado, tipo_medio):
        return False
    all_tokens = _tokens(titulo_resultado)
    if any(word in _RECHAZADOS for word in all_tokens):
        return False

    years = {
        int(t) for t in all_tokens
        if t.isdecimal() and len(t) == 4 and 1870 <= int(t) <= 2200
    }
    if anio is not None:
        if len(years) != 1 or not any(abs(y - anio) <= 1 for y in years):
            return False
    elif len(years) > 1:
        return False

    # Se retira el código del episodio antes de cotejar nombres de series.
    title_no_episode = _EPISODIO_CONCRETO.sub("", titulo_solicitado)
    offered_no_episode = _EPISODIO_CONCRETO.sub("", titulo_resultado)
    raw_offered = _nombre_significativo(offered_no_episode, torrent=False)
    if not raw_offered:
        return False

    for alias in (title_no_episode, *aliases[:20]):
        expected = _nombre_significativo(alias, torrent=False)
        # Una palabra como "Final" puede ser parte real del título.
        # Solo es etiqueta técnica cuando NO pertenece al alias oficial.
        offered_words = {
            word for word in raw_offered
            if word in expected or (
                word not in _ETIQUETAS and not (
                    word.isdecimal() and 1870 <= int(word) <= 2200
                )
            )
        }
        if not expected or not offered_words or offered_words - expected:
            continue
        overlap = len(expected & offered_words)
        required = 1 if len(expected) == 1 else (
            2 if len(expected) <= 3 else max(3, math.ceil(len(expected) * 0.75))
        )
        if overlap >= required:
            return True
    return False
