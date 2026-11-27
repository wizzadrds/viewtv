"""Jellyfin /Sessions: dos GET internos, cero escrituras ni datos privados.

Invocado por viewtv_retirada_jellyfin_probe_run_0021.py, que carga
el módulo guard en memoria durante docker exec, sin alterar la API.
No registra ni publica sesiones de terceros.
"""
from __future__ import annotations

import json

import httpx
from sqlmodel import Session, select
from worker.retirement_playback_guard_0021 import (
    SesionesNoConfiables,
    evaluar_sesiones,
    instantanea_sesiones,
)

from app.config import get_settings
from app.database import engine
from app.models import Medio


def read_sessions(client: httpx.Client) -> list:
    response = client.get("/Sessions")
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise SesionesNoConfiables("Sessions no devolvió una lista.")
    return data


def main() -> int:
    try:
        cfg = get_settings()
        if not cfg.jellyfin_api_key or not cfg.jellyfin_base_url:
            raise SesionesNoConfiables("Jellyfin no configurado.")
        with Session(engine) as db:
            films = db.exec(select(Medio).where(
                Medio.tipo == "pelicula",
                Medio.disponible_en_jellyfin.is_(True),
            )).all()
            movie_ids = [m.jellyfin_id for m in films]
        if not movie_ids:
            raise SesionesNoConfiables("Sin películas que auditar.")
        with httpx.Client(
            base_url=cfg.jellyfin_base_url.rstrip("/"),
            headers={"Authorization": f'MediaBrowser Token="{cfg.jellyfin_api_key}"'},
            timeout=cfg.jellyfin_timeout_seconds,
            follow_redirects=False,
        ) as client:
            first = read_sessions(client)
            second = read_sessions(client)
        if instantanea_sesiones(first) != instantanea_sesiones(second):
            raise SesionesNoConfiables("Sesiones cambiaron durante el GET.")
        result = evaluar_sesiones(second, movie_ids)
        print("JELLYFIN_SESIONES_0021=SOLO_GET")
        for k in (
            "estado", "peliculas_comprobadas", "peliculas_bloqueadas",
            "sesiones_jellyfin", "sesiones_pelicula_objetivo",
            "sesiones_otras_peliculas", "sesiones_ambiguas",
        ):
            print(k.upper() + "=" + str(result[k]))
        print("SIN_BLOQUEO_TRANSACCIONAL=SI")
        print("AUTORIZA_BORRADO_FISICO=NO")
        print("REPRODUCCIONES_MODIFICADAS=0")
        print("ARCHIVOS_ELIMINADOS=0")
        return 0
    except (httpx.HTTPError, ValueError, TypeError, KeyError, OSError, json.JSONDecodeError):
        print("JELLYFIN_SESIONES_0021=FUENTE_NO_VERIFICABLE")
        print("AUTORIZA_BORRADO_FISICO=NO")
        print("REPRODUCCIONES_MODIFICADAS=0")
        print("ARCHIVOS_ELIMINADOS=0")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
