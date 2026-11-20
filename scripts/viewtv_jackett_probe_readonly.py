"""Consulta read-only a la lista de indexadores de Jackett.

Se ejecuta vía stdin dentro del worker activo. No imprime URLs, API keys,
nombres de indexadores, consultas ni resultados torrent. No escribe datos.
"""

from __future__ import annotations

from app.config import get_settings
from app.jackett import JackettClient, JackettError


def categorize(exc: Exception) -> str:
    if isinstance(exc, JackettError):
        message = str(exc).casefold()
        if "configurad" in message:
            return "configuracion_ausente"
        if "comunicaci" in message:
            return "conexion_o_http"
        if "xml" in message or "respuesta" in message:
            return "respuesta_invalida"
        if "torznab" in message or "indexador" in message:
            return "error_del_indexador"
        return "jackett_no_disponible"
    return "excepcion_no_prevista"


def main() -> None:
    s = get_settings()
    print("JACKETT_URL_CONFIGURADA=" + str(bool(s.jackett_base_url)))
    print("JACKETT_CLAVE_CONFIGURADA=" + str(bool(s.jackett_api_key)))
    if not s.jackett_base_url or not s.jackett_api_key:
        print("JACKETT_CONSULTA=OMITIDA_SIN_CONFIGURACION")
        return
    try:
        indexers = JackettClient(settings=s).get_indexers()
        configured = sum(x.configured is True for x in indexers)
        print("JACKETT_CONSULTA=OK")
        print("JACKETT_INDEXADORES_TOTAL=" + str(len(indexers)))
        print("JACKETT_INDEXADORES_CONFIGURADOS=" + str(configured))
    except (JackettError, OSError, TypeError, ValueError) as exc:
        print("JACKETT_CONSULTA=FALLO")
        print("JACKETT_CATEGORIA=" + categorize(exc))


if __name__ == "__main__":
    main()
