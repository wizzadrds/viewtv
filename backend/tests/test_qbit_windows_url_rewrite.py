"""No reescribir URLs ajenas; solo descargas Jackett desde Docker a qBit Windows."""
import pytest
from worker.download_processor import _qbit_url_for_windows_jackett

BASE = "http://host.docker.internal:9117"


@pytest.mark.parametrize(
    "url,base,expected",
    [
        (
            "http://host.docker.internal:9117/dl/fixture?apikey=solo-ficticia",
            BASE,
            "http://127.0.0.1:9117/dl/fixture?apikey=solo-ficticia",
        ),
        (
            "http://host.docker.internal:9117/dl/123?x=1&y=2#fragment",
            BASE,
            "http://127.0.0.1:9117/dl/123?x=1&y=2#fragment",
        ),
        ("magnet:?xt=urn:btih:abcdef", BASE, "magnet:?xt=urn:btih:abcdef"),
        ("https://host.docker.internal:9117/dl/123", BASE, "https://host.docker.internal:9117/dl/123"),
        ("http://host.docker.internal:9117/other/123", BASE, "http://host.docker.internal:9117/other/123"),
        ("http://host.docker.internal:9118/dl/123", BASE, "http://host.docker.internal:9118/dl/123"),
        ("http://127.0.0.1:9117/dl/123", BASE, "http://127.0.0.1:9117/dl/123"),
        ("http://provider.invalid/dl/123", BASE, "http://provider.invalid/dl/123"),
        ("http://host.docker.internal:9117/dl/123", "http://provider.invalid:9117", "http://host.docker.internal:9117/dl/123"),
        ("http://user:password@host.docker.internal:9117/dl/123", BASE, "http://user:password@host.docker.internal:9117/dl/123"),
        ("http://host.docker.internal:9117/dl/123", "https://host.docker.internal:9117", "http://host.docker.internal:9117/dl/123"),
        ("http://host.docker.internal:9117/dl/123", "http://host.docker.internal:9118", "http://host.docker.internal:9117/dl/123"),
    ],
)
def test_rewrite_strict(url, base, expected):
    assert _qbit_url_for_windows_jackett(url, base) == expected
