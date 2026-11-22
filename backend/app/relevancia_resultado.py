"""Filtro conservador de coincidencia de títulos; nunca confía en Torznab.

Un proveedor puede devolver capítulos de series o películas distintas por
palabras parciales. Se compara contra la solicitud antes de mostrar, elegir
o guardar resultados. No se utilizan URL ni hashes para decidir.
"""
from __future__ import annotations

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


def _tokens(value: str) -> list[str]:
    sin_tildes = "".join(
        letter for letter in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(letter)
    )
    # "Nadie2" y "Nadie.2" se analizan igual, pero "Nadie 20" no es "Nadie 2".
    sin_tildes = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", sin_tildes)
    return re.findall(r"[a-z0-9]+", sin_tildes)


def coincide_con_solicitud(
    titulo_solicitado: str,
    tipo_medio: str,
    anio: int | None,
    titulo_resultado: str,
    aliases: tuple[str, ...] = (),
) -> bool:
    """Coincidencia por título solicitado o alias oficial validado de TMDB."""
    candidato = _tokens(titulo_resultado)
    # Para capítulos se conserva obligatoriamente SxxEyy al evaluar
    # nombres originales traducidos de la SERIE.
    codigo = _EPISODIO_CONCRETO.search(titulo_solicitado)
    opciones = [titulo_solicitado]
    for alias in aliases[:20]:
        if alias.strip():
            opciones.append(
                alias + (" " + codigo.group(0) if codigo else "")
                if tipo_medio == "serie" else alias
            )
    matches = [tokens for option in opciones
               if (tokens := _tokens(option)) and candidato[:len(tokens)] == tokens]
    if not matches:
        return False
    largo = max(len(match) for match in matches)
    suffix = candidato[largo:]
    # Que el resultado empiece igual no significa que sea la misma película:
    # «El secreto de otros» no es «El secreto».
    # Tras el título solo admitimos año o etiquetas conocidas de ediciones.
    release_tags = {
        "4k", "8k", "4", "8", "1080", "1080p", "2160", "2160p",
        "720", "720p", "480", "480p", "576", "576p",
        "web", "webrip", "webdl", "bluray", "bdrip", "brrip", "hdrip",
        "hdtv", "dvdrip", "remux", "hd", "uhd", "hdr", "hdr10", "dovi",
        "x264", "x265", "h264", "h265", "hevc", "av1", "aac", "ac3",
        "dts", "ddp", "dolby", "atmos", "multi", "dual", "vose",
        "spanish", "espanol", "castellano", "latino", "sub", "subs",
        "nf", "amzn", "hmax", "dsnp", "imax", "extended", "proper",
        "repack", "uncut", "complete", "director", "edition", "final",
        "esp", "eng", "es", "en", "audio",
    }
    if suffix:
        first = suffix[0]
        legacy_episode = (
            tipo_medio == "serie" and first == "s"
            and _EPISODIO_CONCRETO.search(titulo_resultado) is not None
        )
        if not legacy_episode and first not in release_tags and not (
            first.isdigit() and len(first) == 4 and 1870 <= int(first) <= 2200
        ):
            return False
        if "trailer" in suffix or "teaser" in suffix or "sample" in suffix:
            return False
    if tipo_medio == "pelicula" and _EPISODIO.search(titulo_resultado):
        return False
    if tipo_medio == "serie":
        # Una solicitud S01E02 no puede seleccionar S01E01 ni un pack con
        # capítulos adicionales. Las solicitudes antiguas de serie completa
        # mantienen la comprobación conservadora previa.
        requested = list(_EPISODIO_CONCRETO.finditer(titulo_solicitado))
        if requested:
            offered = list(_EPISODIO_CONCRETO.finditer(titulo_resultado))
            if len(requested) != 1 or len(offered) != 1:
                return False
            expected = requested[0]
            found = offered[0]
            if (
                int(expected["season"]) != int(found["season"])
                or int(expected["episode"]) != int(found["episode"])
            ):
                return False
    # Año de estreno explícito diferente implica versión/obra distinta. Si el
    # resultado no menciona año, no se inventa; queda por revisar en la UI.
    if anio is not None:
        resto = candidato[largo:]
        anios = {int(token) for token in resto if len(token) == 4 and
                 token.isdigit() and 1870 <= int(token) <= 2200}
        if anios and anio not in anios:
            return False
    return True
