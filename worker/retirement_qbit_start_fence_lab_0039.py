"""0039: cercado transaccional del inicio VIEWTV, solo SQLite TEMP y qBit mock.

La misma BEGIN IMMEDIATE que reserva la custodia 0038 protege el POST
start_torrent ejecutado por este adaptador de laboratorio. Si existe una
custodia para el hash, incluso 'registrada', no puede emitirse START.
Ninguna aplicación de producción importa este módulo y la GUI de qBit
no consulta esta barrera, por lo que NO autoriza retirar archivos.
"""
from __future__ import annotations

import re
import sqlite3

import httpx

from worker.retirement_qbit_start_intent_lab_0046 import (
    InicioAmbiguo0046,
    comprobar_inicio_0046,
    estado_inicio_0046,
    hubo_inicio_0046,
)
from worker.retirement_qbit_stop_lab_0038 import (
    CustodiaQbitLab0038,
    ParadaLabRechazada,
)

_HASH = re.compile(r"(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})\Z")


class InicioCustodiadoLab0039:
    """Adaptador inyectable al trabajador; no altera su ruta productiva."""

    def __init__(self, custodia: CustodiaQbitLab0038) -> None:
        if not isinstance(custodia, CustodiaQbitLab0038):
            raise ParadaLabRechazada("Falta autoridad de laboratorio.")
        if not isinstance(
            getattr(custodia.qbit, "_transport", None), httpx.MockTransport
        ):
            raise ParadaLabRechazada("No se puede usar qBittorrent real.")
        self.custodia = custodia
        self.qbit = custodia.qbit

    def torrents_info(self, hashes=None, *, tag=None):
        """La misma fuente simulada que usa el worker VIEWTV."""
        if not isinstance(
            getattr(self.qbit, "_transport", None), httpx.MockTransport
        ):
            raise ParadaLabRechazada("Se ha cambiado el transporte ficticio.")
        return self.qbit.torrents_info(hashes, tag=tag)

    def start_torrent(self, hash_: str) -> None:
        """Persistir intención de START ANTES del POST simulado.

        Un cierre de proceso tras la intención y antes, durante o después
        del POST deja entrada durable. Ninguna alta de custodia del MISMO
        hash puede usar un snapshot anterior ni asumir quietud.
        """
        if not isinstance(hash_, str) or _HASH.fullmatch(hash_) is None:
            raise ParadaLabRechazada("Hash de inicio no verificable.")
        if not isinstance(
            getattr(self.qbit, "_transport", None), httpx.MockTransport
        ):
            raise ParadaLabRechazada("Se ha cambiado el transporte ficticio.")
        target = hash_.casefold()
        try:
            with self.custodia._tx() as conn:
                comprobar_inicio_0046(conn)
                blocked = conn.execute(
                    "SELECT COUNT(*) FROM custodia WHERE lower(hash)=?",
                    (target,),
                ).fetchone()
                if blocked is None or blocked[0] not in (0, 1):
                    raise ParadaLabRechazada("Diario inconsistente.")
                if blocked[0] or hubo_inicio_0046(conn, target):
                    raise ParadaLabRechazada(
                        "START previo o custodia: se exige reconciliación."
                    )
                # COMMIT de intención al cerrar _tx, ANTES de cualquier POST.
                conn.execute(
                    "INSERT INTO inicios_qbit_0046(hash,estado) "
                    "VALUES(?,'pendiente')",
                    (target,),
                )
            with self.custodia._tx() as conn:
                comprobar_inicio_0046(conn)
                row = conn.execute(
                    "SELECT estado FROM inicios_qbit_0046 WHERE hash=?",
                    (target,),
                ).fetchone()
                if row != ("pendiente",):
                    raise ParadaLabRechazada(
                        "Intención START distinta antes de POST."
                    )
                count = conn.execute(
                    "SELECT COUNT(*) FROM custodia WHERE lower(hash)=?",
                    (target,),
                ).fetchone()
                if count != (0,):
                    raise ParadaLabRechazada("Custodia apareció antes del POST.")
                if not isinstance(
                    getattr(self.qbit, "_transport", None),
                    httpx.MockTransport,
                ):
                    raise ParadaLabRechazada("Transporte real no permitido.")
                self.qbit.start_torrent(target)
                conn.execute(
                    "UPDATE inicios_qbit_0046 "
                    "SET estado='confirmada' WHERE hash=? AND estado='pendiente'",
                    (target,),
                )
        except (sqlite3.Error, InicioAmbiguo0046) as exc:
            raise ParadaLabRechazada("Bitácora START no disponible.") from exc

    def estado_intencion(self, hash_: str) -> dict:
        """Consultar la barrera durable; NUNCA concede permiso de retirada."""
        try:
            with self.custodia._tx() as conn:
                return estado_inicio_0046(conn, hash_)
        except (sqlite3.Error, InicioAmbiguo0046) as exc:
            raise ParadaLabRechazada(
                "Intención START no verificable."
            ) from exc

    def estado_custodia(self, descarga_id: int) -> dict:
        """Solo observación, jamás un permiso físico."""
        data = self.custodia.estado(descarga_id)
        return {
            "estado": data["estado"],
            "puede_reiniciar_torrent_custodiado": False,
            "controla_otras_interfaces_qbit": False,
            "autoriza_borrado_fisico": False,
        }
