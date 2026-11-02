"""Crea un perfil local solicitando el PIN sin mostrarlo en pantalla."""

from getpass import getpass

from sqlmodel import Session, select

from app.auth import hash_pin
from app.database import engine
from app.models import Perfil


def main() -> None:
    nombre = input("Nombre del perfil: ").strip()
    if not nombre or len(nombre) > 40:
        raise SystemExit("El nombre debe tener entre 1 y 40 caracteres.")

    pin = getpass("PIN (4-8 dígitos): ")
    confirmacion = getpass("Repite el PIN: ")
    if pin != confirmacion:
        raise SystemExit("Los PIN no coinciden.")

    try:
        pin_hash = hash_pin(pin)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    with Session(engine) as session:
        existing = session.exec(select(Perfil).where(Perfil.nombre == nombre)).first()
        if existing is not None:
            raise SystemExit("Ya existe un perfil con ese nombre.")
        session.add(Perfil(nombre=nombre, pin_hash=pin_hash))
        session.commit()

    print(f"Perfil «{nombre}» creado correctamente.")


if __name__ == "__main__":
    main()
