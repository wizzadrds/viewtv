"""HTTP pruebas GET con copia real SQLite sólo lectura; sin imprimir contenido."""
from types import SimpleNamespace

from app.auth import get_current_profile
from app.main import app
from fastapi.testclient import TestClient

with TestClient(app) as client:
    for path in ("/health", "/descubrir/filas", "/descubrir/filas/recientes"):
        result = client.get(path)
        print("UNAUTH_PATH=" + path + " STATUS=" + str(result.status_code))
    app.dependency_overrides[get_current_profile] = lambda: SimpleNamespace(id=1)
    try:
        for path in ("/descubrir/filas", "/descubrir/filas/recientes", "/descubrir/estado"):
            result = client.get(path)
            print("AUTH_PATH=" + path + " STATUS=" + str(result.status_code))
            if result.status_code == 200 and path == "/descubrir/filas/recientes":
                print("LOCAL_ITEM_COUNT="+str(len(result.json().get("elementos", []))))
    finally:
        app.dependency_overrides.clear()
