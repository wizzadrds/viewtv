from app.config import get_settings


def test_settings_read_download_services_environment(monkeypatch):
    monkeypatch.setenv("JACKETT_BASE_URL", "http://jackett.test:9117")
    monkeypatch.setenv("JACKETT_API_KEY", "jackett-test-key")
    monkeypatch.setenv("JACKETT_TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("QBITTORRENT_BASE_URL", "http://qbittorrent.test:8080")
    monkeypatch.setenv("QBITTORRENT_API_KEY", "qbt_test_key")
    monkeypatch.setenv("QBITTORRENT_TIMEOUT_SECONDS", "15")

    get_settings.cache_clear()
    try:
        settings = get_settings()

        assert settings.jackett_base_url == "http://jackett.test:9117"
        assert settings.jackett_api_key == "jackett-test-key"
        assert settings.jackett_timeout_seconds == 25
        assert settings.qbittorrent_base_url == "http://qbittorrent.test:8080"
        assert settings.qbittorrent_api_key == "qbt_test_key"
        assert settings.qbittorrent_timeout_seconds == 15
    finally:
        get_settings.cache_clear()
