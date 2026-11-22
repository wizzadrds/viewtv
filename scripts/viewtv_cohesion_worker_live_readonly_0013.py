"""Diagnóstico solo consultas. NUNCA imprime títulos hallados, URLs ni descarga."""
from app.jackett import JackettClient, JackettError
from app.relevancia_resultado import coincide_con_solicitud
from app.titulo_cohesion import aliases_para_solicitud, consultas_jackett

title = "Vengadores: Doomsday"
year = 2026
aliases = aliases_para_solicitud(title, "pelicula", year)
assert any("avengers" in x.casefold() for x in aliases), "No se enlazó el título original."
queries = consultas_jackett(title, "pelicula", year, aliases)
assert len(queries) <= 4
assert queries[0].startswith("Vengadores")
assert any("Avengers" in q for q in queries)
assert "Doomsday" == queries[-1], queries
print("TMDB_ALIASES_OFICIALES="+str(len(aliases)))
print("JACKETT_CONSULTAS="+str(len(queries)))
print("CONSULTA_IDIOMA_INGLES=SI")
print("CONSULTA_SUBTITULO_Doomsday=SI")

client = JackettClient()
found = 0
accepted = 0
errors = 0
for query in queries:
    try:
        data = client.search(query, search_type="movie")
        count = len(data)
        okay = sum(
            coincide_con_solicitud(title, "pelicula", year, item.title, aliases)
            for item in data
        )
        found += count
        accepted += okay
        print("CONSULTA_TORZNAB_RESULTADOS="+str(count)+" COINCIDEN="+str(okay))
    except JackettError:
        errors += 1
        print("CONSULTA_TORZNAB=NO_DISPONIBLE")
print("TOTAL_RESPUESTAS_SIN_DEDUPLICAR="+str(found))
print("TOTAL_COINCIDENCIAS_VERIFICADAS="+str(accepted))
print("CONSULTAS_FALLIDAS="+str(errors))
print("DESCARGAS_INICIADAS=0")
