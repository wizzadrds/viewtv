"""Cliente HTTP para la API v3 de The Movie Database."""

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

    @staticmethod
    def image_url(path: str | None, size: str) -> str | None:
        if not path or not path.startswith("/") or ".." in path:
            return None
        if size not in {"w500", "w780", "w1280", "original"}:
            return None
        return f"{TMDB_IMAGE_URL}/{size}{path}"
