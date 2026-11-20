"""Filtro conservador de coincidencia de títulos; nunca confía en Torznab.

Un proveedor puede devolver capítulos de series o películas distintas por
palabras parciales. Se compara contra la solicitud antes de mostrar, elegir
o guardar resultados. No se utilizan URL ni hashes para decidir.
"""
from __future__ import annotations

import re
import unicodedata

_EPISODIO = re.compile(
    r"(?<![A-Z0-9])(?:S\d{1,2}[. _-]*E\d{1,3}|S\d{1,2}|\d{1,2}X\d{1,3})(?![A-Z0-9])",
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
) -> bool:
    """Conservador: solo coincidencia inequívoca; lo dudoso no es seleccionable."""
    esperado = _tokens(titulo_solicitado)
    candidato = _tokens(titulo_resultado)
    if not esperado or candidato[: len(esperado)] != esperado:
        return False
    if tipo_medio == "pelicula" and _EPISODIO.search(titulo_resultado):
        return False
    # Año de estreno explícito diferente implica versión/obra distinta. Si el
    # resultado no menciona año, no se inventa; queda por revisar en la UI.
    if anio is not None:
        resto = candidato[len(esperado):]
        anios = {int(token) for token in resto if len(token) == 4 and
                 token.isdigit() and 1870 <= int(token) <= 2200}
        if anios and anio not in anios:
            return False
    return True
