from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth import limiter
from app.auth import router as auth_router
from app.config import get_settings
from app.jellyfin import router as jellyfin_router
from app.jellyfin_playback import router as jellyfin_playback_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router)
app.include_router(jellyfin_router)
app.include_router(jellyfin_playback_router)


@app.get("/health", tags=["sistema"])
def health() -> dict[str, str]:
    return {"estado": "ok", "servicio": "viewtv-api"}
