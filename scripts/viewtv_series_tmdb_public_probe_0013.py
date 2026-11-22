"""Prueba solo GET de metadatos TMDB reales; no imprime títulos o claves.

Ejecutar en la API autorizada, sin modificar SQLite ni descargar vídeos.
"""
from app.tmdb import TMDBClient

client = TMDBClient()
show = client.details("serie", 1396)
assert show.get("id") == 1396
seasons = show.get("seasons")
assert isinstance(seasons, list)
assert any(isinstance(s, dict) and s.get("season_number") == 1 for s in seasons)
season = client._get("tv/1396/season/1")
assert season.get("season_number") == 1
episodes = season.get("episodes")
assert isinstance(episodes, list) and len(episodes) >= 1
assert all(isinstance(e, dict) for e in episodes)
assert any(e.get("episode_number") == 1 for e in episodes)
print("TMDB_SERIE_TEMPORADAS_REALES=OK")
print("TMDB_TEMPORADA_EPISODIOS_REALES=OK")
print("TEMPORADAS="+str(len(seasons)))
print("EPISODIOS_TEMPORADA_1="+str(len(episodes)))
print("DESCARGAS_INICIADAS=0")
