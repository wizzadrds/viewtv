from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from app.config import get_settings
from app.database import get_session
from app.models import Perfil

router = APIRouter(prefix="/auth", tags=["autenticación"])
limiter = Limiter(key_func=get_remote_address)
password_hasher = PasswordHasher()
# Hash ficticio para que un nombre inexistente también requiera una verificación Argon2.
_dummy_pin_hash = password_hasher.hash("VIEWTV-invalid-pin-dummy")


class LoginInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=40)
    pin: str = Field(pattern=r"^\d{4,8}$")


def hash_pin(pin: str) -> str:
    if not pin.isdigit() or not 4 <= len(pin) <= 8:
        raise ValueError("El PIN debe contener entre 4 y 8 dígitos.")
    return password_hasher.hash(pin)


def verify_pin(pin_hash: str, pin: str) -> bool:
    try:
        return password_hasher.verify(pin_hash, pin)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(profile_id: int) -> str:
    settings = get_settings()
    if len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET debe contener al menos 32 caracteres.")
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": str(profile_id), "iat": now, "exp": expires_at},
        settings.jwt_secret,
        algorithm="HS256",
    )


def get_current_profile(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Perfil:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación necesaria.",
        )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub"]},
        )
        profile_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida o caducada.",
        ) from None

    profile = session.get(Perfil, profile_id)
    if profile is None or not profile.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil no disponible.",
        )
    return profile


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,
    payload: LoginInput,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    settings = get_settings()
    profile = session.exec(select(Perfil).where(Perfil.nombre == payload.nombre)).first()
    pin_hash = profile.pin_hash if profile is not None else _dummy_pin_hash

    if not verify_pin(pin_hash, payload.pin) or profile is None or not profile.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil o PIN incorrectos.",
        )

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_access_token(profile.id),
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )
    return {"estado": "autenticado", "perfil": {"id": profile.id, "nombre": profile.nombre}}


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )
    return {"estado": "sesión_cerrada"}


@router.get("/me")
def me(
    profile: Annotated[Perfil, Depends(get_current_profile)],
) -> dict[str, object]:
    return {"id": profile.id, "nombre": profile.nombre}
