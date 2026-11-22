"""Cliente HTTP para la API v3 de The Movie Database."""

from datetime import UTC, datetime

import httpx

from app.config import get_settings

TMDB_API_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p"


class TMDBError(Exception):
    """Error controlado de comunicación con TMDB."""


class TMDBClient:
    """Cliente mínimo para buscar y consultar películas y series."""

    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.tmdb_api_key:
            raise TMDBError("La clave de TMDB no está configurada.")

    def _get(self, path: str, params: dict | None = None) -> dict:
        query = {
            "api_key": self.settings.tmdb_api_key,
            "language": self.settings.tmdb_language,
            **(params or {}),
        }
        try:
            response = httpx.get(
                f"{TMDB_API_URL}/{path.lstrip('/')}",
                params=query,
                timeout=self.settings.tmdb_timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TMDBError("No se pudo consultar TMDB.") from exc

        if not isinstance(data, dict):
            raise TMDBError("TMDB devolvió una respuesta no válida.")
        return data

    def trending(self, media_type: str, page: int = 1) -> dict:
        """Novedades de metadatos; no consulta ni inicia descargas."""
        kinds = {"pelicula": "movie", "serie": "tv"}
        if media_type not in kinds or not 1 <= page <= 10:
            raise TMDBError("Tipo o página no válidos para TMDB.")
        return self._get(f"trending/{kinds[media_type]}/week", {"page": page})

    def discover(
        self,
        media_type: str,
        *,
        genre_id: int | None = None,
        release_year: int | None = None,
        page: int = 1,
    ) -> dict:
        """Filtros de metadatos TMDB; jamás envía trabajos a qBittorrent."""
        kinds = {"pelicula": "movie", "serie": "tv"}
        if media_type not in kinds or not 1 <= page <= 500:
            raise TMDBError("Tipo o página no válidos.")
        allowed_genres = {
            "pelicula": {28, 27, 35, 18, 53, 878, 12, 16},
            "serie": {18, 35, 80, 9648, 10759, 10765},
        }
        if genre_id is not None and genre_id not in allowed_genres[media_type]:
            raise TMDBError("Género no permitido.")
        if release_year is not None:
            current_year = datetime.now(UTC).year
            if media_type != "pelicula" or not 1900 <= release_year <= current_year:
                raise TMDBError("Año de estreno no válido.")
        params: dict[str, str | int] = {
            "page": page,
            "sort_by": "popularity.desc",
            "include_adult": "false",
            "include_video": "false",
        }
        if genre_id is not None:
            params["with_genres"] = genre_id
        if release_year is not None:
            params["primary_release_year"] = release_year
            params["primary_release_date.lte"] = datetime.now(UTC).date().isoformat()
        return self._get(f"discover/{kinds[media_type]}", params)

    def search_page(self, media_type: str, title: str, page: int = 1) -> dict:
        """Búsqueda de metadatos paginada, separada de Jackett/qBittorrent."""
        kinds = {"pelicula": "movie", "serie": "tv"}
        if media_type not in kinds or not 1 <= page <= 10 or not 2 <= len(title.strip()) <= 100:
            raise TMDBError("Parámetros de búsqueda no válidos.")
        return self._get(
            f"search/{kinds[media_type]}",
            {"query": title.strip(), "page": page, "include_adult": "false"},
        )

    def search(self, media_type: str, title: str, year: int | None = None) -> list[dict]:
        endpoints = {
            "pelicula": "search/movie",
            "serie": "search/tv",
        }
        if media_type not in endpoints:
            raise TMDBError("Tipo de medio no compatible con TMDB.")

        params: dict[str, str | int] = {"query": title}
        if year:
            params["primary_release_year" if media_type == "pelicula"
                   else "first_air_date_year"] = year

        data = self._get(endpoints[media_type], params)
        results = data.get("results", [])
        return [item for item in results if isinstance(item, dict)] if isinstance(
            results, list
        ) else []

    def details(self, media_type: str, tmdb_id: int) -> dict:
        endpoints = {
            "pelicula": "movie",
            "serie": "tv",
        }
        if media_type not in endpoints or tmdb_id <= 0:
            raise TMDBError("Identificador o tipo de medio no válido.")
        return self._get(f"{endpoints[media_type]}/{tmdb_id}")

    def details_with_aliases(self, media_type: str, tmdb_id: int) -> dict:
        """Una única consulta TMDB para ficha, traducciones y títulos oficiales."""
        kinds = {"pelicula": "movie", "serie": "tv"}
        if media_type not in kinds or type(tmdb_id) is not int or not 1 <= tmdb_id <= 2_147_483_647:
            raise TMDBError("Tipo o identificador no válido.")
        return self._get(
            f"{kinds[media_type]}/{tmdb_id}",
            {"append_to_response": "translations,alternative_titles"},
        )

    def season_details(self, tmdb_id: int, season_number: int) -> dict:
        """Episodios de una temporada; solo consulta metadatos TMDB."""
        if (
            type(tmdb_id) is not int or not 1 <= tmdb_id <= 2_147_483_647
            or type(season_number) is not int or not 0 <= season_number <= 100
        ):
            raise TMDBError("Identificador de serie o temporada no válido.")
        return self._get(f"tv/{tmdb_id}/season/{season_number}")

    @staticmethod
    def image_url(path: str | None, size: str) -> str | None:
        if not path or not path.startswith("/") or ".." in path:
            return None
        if size not in {"w500", "w780", "w1280", "original"}:
            return None
        return f"{TMDB_IMAGE_URL}/{size}{path}"
