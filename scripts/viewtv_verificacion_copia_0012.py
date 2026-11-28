"""Ensayo de transición de verificación en una COPIA SQLite, sin qBittorrent.

Lee la copia y la clona a memoria; ejecuta el método real del worker
con el modelo/revisión 0012, que no tienen campos de organización.
"""
import os
import sqlite3
from datetime import UTC, datetime, timedelta

from app.models import Descarga
from app.queue import finish_claimed_verification
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine


def main():
    assert os.environ.get("VIEWTV_VERIFICATION_COMPAT_SANDBOX") == "1"
    assert not os.path.exists("/data/viewtv.db")
    conn = sqlite3.connect("file:/copia/viewtv.db?mode=ro", uri=True)
    memory = sqlite3.connect(":memory:", check_same_thread=False)
    conn.backup(memory)
    conn.close()
    memory.execute("PRAGMA foreign_keys=ON")
    engine=create_engine("sqlite://",poolclass=StaticPool,creator=lambda:memory)
    with Session(engine) as session:
        row=session.get(Descarga,2)
        assert row is not None
        assert row.estado=="completada" and row.progreso==1
        assert row.estado_verificacion=="pendiente"
        assert row.qbittorrent_hash
        assert not hasattr(row,"organizacion_estado")
        row.verificacion_locked_by="compat-sandbox"
        row.verificacion_locked_until=datetime.now(UTC)+timedelta(minutes=3)
        session.add(row)
        session.commit()
        assert finish_claimed_verification(
            session,2,row.qbittorrent_hash,"compat-sandbox",verified=True,
        )
        session.expire_all()
        row=session.get(Descarga,2)
        assert row.estado_verificacion=="verificada"
        assert row.verificada_en is not None
        assert row.verificacion_locked_by is None
        assert not hasattr(row,"organizacion_estado")
        print("PASS_FINALIZA_VERIFICACION_EN_ESQUEMA_0012")
        print("PASS_NO_ALTERA_ORGANIZACION_0013")
        assert session.get(Descarga,1).estado=="fallida"
        print("PASS_HISTORICO_INALTERADO")
    engine.dispose()

if __name__=="__main__":
    main()
