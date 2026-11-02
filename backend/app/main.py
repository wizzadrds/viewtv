from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    return {"estado": "ok", "servicio": "viewtv-api"}
