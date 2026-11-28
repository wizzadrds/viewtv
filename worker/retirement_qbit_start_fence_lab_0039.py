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
        """Serializa START con el alta del cerco en la misma base SQLite.

        Retiene la transacción hasta terminar el POST simulado. Cualquier
        cierre de proceso durante el POST implica que hay que reconciliar
        el resultado antes de operar; nunca se autoriza borrado.
        """
        if not isinstance(hash_, str) or _HASH.fullmatch(hash_) is None:
            raise ParadaLabRechazada("Hash de inicio no verificable.")
        if not isinstance(
            getattr(self.qbit, "_transport", None), httpx.MockTransport
        ):
            raise ParadaLabRechazada("Se ha cambiado el transporte ficticio.")
        try:
            with self.custodia._tx() as conn:
                # Rechazar incluso si otra fila/custodia aparece con una
                # variante de mayúsculas del mismo hash.
                blocked = conn.execute(
                    "SELECT COUNT(*) FROM custodia WHERE lower(hash)=?",
                    (hash_.casefold(),),
                ).fetchone()
                if blocked is None or blocked[0] not in (0, 1):
                    raise ParadaLabRechazada("Diario inconsistente.")
                if blocked[0] != 0:
                    raise ParadaLabRechazada(
                        "Inicio denegado por custodia de retirada."
                    )
                self.qbit.start_torrent(hash_)
        except sqlite3.Error as exc:
            raise ParadaLabRechazada("Barrera SQLite no disponible.") from exc

    def estado_custodia(self, descarga_id: int) -> dict:
        """Solo observación, jamás un permiso físico."""
        data = self.custodia.estado(descarga_id)
        return {
            "estado": data["estado"],
            "puede_reiniciar_torrent_custodiado": False,
            "controla_otras_interfaces_qbit": False,
            "autoriza_borrado_fisico": False,
        }
