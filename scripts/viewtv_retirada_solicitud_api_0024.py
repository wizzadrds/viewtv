"""Consultar una película concreta en la SQLite API: ESTRICTAMENTE lectura.

Dentro de viewtv-api-1 con 'python - <titulo> <anio>' via código stdin.
No muestra nombres, perfiles ni rutas; solo JSON privado para WSL.
No importa endpoints autenticados ni modifica solicitudes/descargas.
"""
from __future__ import annotations

import json
import sys

from sqlmodel import Session, select

from app.database import engine
from app.models import Medio, PeliculaVista, Perfil, SolicitudRetirada


def consulta(titulo: str, anio: int) -> dict:
    if not isinstance(titulo, str) or not 1 <= len(titulo) <= 500:
        raise ValueError("Título de revisión inválido.")
    if not isinstance(anio, int) or isinstance(anio, bool) or not 1870 <= anio <= 2200:
        raise ValueError("Año de revisión inválido.")
    with Session(engine) as session:
        movies = session.exec(
            select(Medio).where(
                Medio.tipo == "pelicula",
                Medio.disponible_en_jellyfin.is_(True),
                Medio.titulo == titulo,
                Medio.anio == anio,
            ),
        ).all()
        if len(movies) != 1 or movies[0].id is None:
            return {"estado": "pelicula_no_unica", "coincidencias": len(movies)}
        media = movies[0]
        profiles = session.exec(
            select(Perfil).where(Perfil.activo.is_(True))
        ).all()
        active = {
            p.id for p in profiles if type(p.id) is int and p.id > 0
        }
        if not active or len(active) != len(profiles):
            return {"estado": "perfiles_no_verificables"}
        marks = session.exec(
            select(PeliculaVista).where(PeliculaVista.medio_id == media.id)
        ).all()
        requests = session.exec(
            select(SolicitudRetirada).where(
                SolicitudRetirada.medio_id == media.id,
            ),
        ).all()
        watched = [
            p.perfil_id for p in marks if p.perfil_id in active
        ]
        pending = [
            p.perfil_id for p in requests
            if p.perfil_id in active and p.estado == "pendiente_revision"
        ]
        if len(watched) != len(set(watched)) or len(pending) != len(set(pending)):
            return {"estado": "filas_perfiles_duplicadas"}
        if any(p.estado not in ("pendiente_revision", "cancelada") for p in requests):
            return {"estado": "estado_retirada_ambiguo"}
        return {
            "estado": "unica",
            "medio_id": media.id,
            "jellyfin_id": media.jellyfin_id,
            "perfiles_activos": sorted(active),
            "visto_perfiles": sorted(watched),
            "pendiente_perfiles": sorted(pending),
            "solicitudes_canceladas": sum(
                p.perfil_id in active and p.estado == "cancelada"
                for p in requests
            ),
        }


def main() -> None:
    if len(sys.argv) != 3 or not sys.argv[2].isascii() or not sys.argv[2].isdecimal():
        raise SystemExit(2)
    try:
        result = consulta(sys.argv[1], int(sys.argv[2]))
    except (ValueError, TypeError):
        raise SystemExit(2) from None
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
