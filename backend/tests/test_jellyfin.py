from datetime import UTC, datetime

import httpx
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import Settings
from app.jellyfin import JellyfinClient, _upsert_media
from app.models import Medio


def make_settings() -> Settings:
    return Settings(
        jellyfin_base_url="http://jellyfin.test:8096",
        jellyfin_api_key="test-secret",
        jellyfin_timeout_seconds=5,
    )


def test_jellyfin_client_uses_mediabrowser_authentication():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == 'MediaBrowser Token="test-secret"'
        assert request.url.path == "/System/Info"
        return httpx.Response(200, json={"ServerName": "VIEWTV-test", "Version": "12.4.0"})

    client = JellyfinClient(make_settings(), httpx.MockTransport(handler))
    assert client.system_info()["ServerName"] == "VIEWTV-test"


def test_jellyfin_items_request_is_recursive_and_limited():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/Items"
        assert request.url.params["Recursive"] == "true"
        assert request.url.params["IncludeItemTypes"] == "Movie,Series"
        assert request.url.params["StartIndex"] == "100"
        assert request.url.params["Limit"] == "100"
        return httpx.Response(200, json={"Items": [], "TotalRecordCount": 0})

    client = JellyfinClient(make_settings(), httpx.MockTransport(handler))
    assert client.get_items(100, 100)["Items"] == []


def test_upsert_media_persists_metadata_without_video_files():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    item = {
        "Id": "jf-movie-1",
        "Type": "Movie",
        "Name": "Película de prueba",
        "Overview": "Sinopsis",
        "ProductionYear": 2024,
        "Genres": ["Drama", "Ciencia ficción"],
        "ImageTags": {"Primary": "tag"},
        "BackdropImageTags": ["tag"],
    }

    with Session(engine) as session:
        now = datetime.now(UTC)
        assert _upsert_media(session, item, now)
        session.commit()
        media = session.exec(select(Medio)).one()
        assert media.jellyfin_id == "jf-movie-1"
        assert media.tipo == "pelicula"
        assert media.anio == 2024
        assert media.generos == ["Drama", "Ciencia ficción"]
        assert media.imagen_portada == "/Items/jf-movie-1/Images/Primary"
        assert media.imagen_fondo == "/Items/jf-movie-1/Images/Backdrop/0"
        assert not hasattr(media, "archivo_video")


def test_upsert_ignores_non_movie_and_non_series_items():
    assert not _upsert_media(
        Session(create_engine("sqlite://")),
        {"Id": "jf-1", "Type": "Episode", "Name": "Episodio"},
        datetime.now(UTC),
    )



def test_jellyfin_client_downloads_only_allowed_image_types():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/Items/jf-movie-1/Images/Primary"
        assert request.headers["Authorization"] == 'MediaBrowser Token="test-secret"'
        assert "image/jpeg" in request.headers["Accept"]
        return httpx.Response(
            200,
            content=b"jpeg-data",
            headers={"Content-Type": "image/jpeg"},
        )

    client = JellyfinClient(make_settings(), httpx.MockTransport(handler))
    assert client.get_image("jf-movie-1", "primary") == (b"jpeg-data", "image/jpeg")


def test_jellyfin_client_rejects_non_image_content_type():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<script>", headers={"Content-Type": "text/html"})

    client = JellyfinClient(make_settings(), httpx.MockTransport(handler))
    from app.jellyfin import JellyfinError

    try:
        client.get_image("jf-movie-1", "primary")
    except JellyfinError as exc:
        assert "formato de imagen" in str(exc)
    else:
        raise AssertionError("Se esperaba rechazar el tipo de contenido.")
