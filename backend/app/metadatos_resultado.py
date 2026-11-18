
"""Extracción de metadatos técnicos desde títulos de torrents."""

import re


def extraer_metadatos(titulo: str) -> dict[str, str | None]:
    texto = titulo.upper()

    resoluciones = [
        (r"(?<!\d)2160P(?!\d)|\b4K\b|\bUHD\b", "2160p", "4K"),
        (r"(?<!\d)1080P(?!\d)", "1080p", "Full HD"),
        (r"(?<!\d)720P(?!\d)", "720p", "HD"),
        (r"(?<!\d)576P(?!\d)", "576p", "SD"),
        (r"(?<!\d)480P(?!\d)", "480p", "SD"),
    ]

    resolucion = None
    calidad = "No especificada"

    for patron, valor, etiqueta in resoluciones:
        if re.search(patron, texto):
            resolucion = valor
            calidad = etiqueta
            break

    fuentes = [
        (r"\bBLURAY\b|\bBLU-RAY\b", "BluRay"),
        (r"\bBDRIP\b", "BDRip"),
        (r"\bBRRIP\b", "BRRip"),
        (r"\bWEB[-_. ]?DL\b", "WEB-DL"),
        (r"\bWEB[-_. ]?RIP\b", "WEBRip"),
        (r"\bHDRIP\b", "HDRip"),
        (r"\bDVDRIP\b", "DVDRip"),
        (r"\bHDTV\b", "HDTV"),
    ]

    fuente = next(
        (valor for patron, valor in fuentes if re.search(patron, texto)),
        None,
    )

    codecs = [
        (r"\bHEVC\b|\bX265\b|\bH[.]265\b", "HEVC"),
        (r"\bX264\b|\bH[.]264\b|\bAVC\b", "H.264"),
        (r"\bAV1\b", "AV1"),
    ]

    codec = next(
        (valor for patron, valor in codecs if re.search(patron, texto)),
        None,
    )

    if re.search(r"\bDUAL\b|\bMULTI\b", texto):
        idioma = "Dual/Multi"
    elif re.search(r"\bSPANISH\b|\bCASTELLANO\b|\bESPA[NÑ]OL\b", texto):
        idioma = "Español"
    elif re.search(r"\bLATINO\b|\bLAT\b", texto):
        idioma = "Latino"
    elif re.search(r"\bVO\b|\bVOS\b|\bSUBS?\b", texto):
        idioma = "VO/Subtitulada"
    else:
        idioma = None

    return {
        "resolucion": resolucion,
        "calidad": calidad,
        "fuente": fuente,
        "codec": codec,
        "idioma": idioma,
    }
