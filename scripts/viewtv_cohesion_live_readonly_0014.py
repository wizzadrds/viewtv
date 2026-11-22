"""Comprobar la cohesión desplegada sin solicitudes, metainfo ni descargas.

Nunca muestra claves, URLs, títulos devueltos por proveedores o hashes.
"""
from app.jackett import JackettClient, JackettError
from app.relevancia_resultado import coincide_con_solicitud
from app.titulo_cohesion import aliases_para_solicitud, consultas_jackett

client = JackettClient()
cases = (
    ("DOOMSDAY", "Vengadores: Doomsday", 2026, 1003596, 6),
    ("OCHO_APELLIDOS", "Ocho apellidos vascos", 2014, None, 2),
)
for label, title, year, identity, limit in cases:
    if identity is None:
        aliases = aliases_para_solicitud(title, "pelicula", year)
    else:
        aliases = aliases_para_solicitud(title, "pelicula", year, identity)
    queries = consultas_jackett(title, "pelicula", year, aliases)
    assert len(queries) <= 6
    total = valid = failed = 0
    for query in queries[:limit]:
        try:
            rows = client.search(query, search_type="movie")
        except JackettError:
            failed += 1
            continue
        total += len(rows)
        valid += sum(
            coincide_con_solicitud(title, "pelicula", year, row.title, aliases)
            for row in rows
        )
    print(f"{label}_ALIAS_OFICIALES={len(aliases)}")
    print(f"{label}_CONSULTAS_LEIDAS={min(len(queries), limit)}")
    print(f"{label}_RESULTADOS_BRUTOS={total}")
    print(f"{label}_COINCIDENCIAS_TEXTO_Y_ANIO={valid}")
    print(f"{label}_CONSULTAS_FALLIDAS={failed}")
print("OPERACIONES_GET_JACKETT=SI")
print("SOLICITUDES_Y_TORRENTS_CREADOS=0")
