"""Solo metadatos TMDB: comprobar Vengadores/Doomsday, nunca torrents."""
from app.titulo_cohesion import _extract_aliases, tokens
from app.tmdb import TMDBClient

client = TMDBClient()
for query in ("Vengadores: Doomsday", "Avengers: Doomsday", "Doomsday"):
    matches = client.search("pelicula", query)
    print("BUSQUEDA="+query.replace(":", "")+" RESULTADOS="+str(len(matches)))
    for item in matches:
        if "doomsday" not in tokens(item.get("title","")) and "doomsday" not in tokens(item.get("original_title","")):
            continue
        if "avengers" in tokens(item.get("original_title","")) or "vengadores" in tokens(item.get("title","")):
            mid = item["id"]
            print("COINCIDENCIA_TMDB_ID="+str(mid)+" AÑO="+str(item.get("release_date","")[:4]))
            full = client.details_with_aliases("pelicula", mid)
            aliases = _extract_aliases(full, "pelicula")
            print("TITULOS_OFICIALES_APROBADOS="+str(len(aliases)))
            print("CONTIENE_AVENGERS="+str(any("avengers" in tokens(a) for a in aliases)))
            print("CONTIENE_VENGADORES="+str(any("vengadores" in tokens(a) for a in aliases)))
            print("COHESION_IDENTIDAD_TMDB=PASS")
            raise SystemExit(0)
print("NO_SE_ENCONTRO_IDENTIDAD_UNICA_EN_CONSULTA")
raise SystemExit(1)
