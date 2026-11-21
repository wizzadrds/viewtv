"""Diagnóstico de solo lectura para la descarga 3, sin publicar ni mostrar secretos.
Se introduce por STDIN en el contenedor API ya configurado: no escribe código allí.
"""
from pathlib import Path
from sqlmodel import Session
from app.database import engine
from app.models import Descarga, Solicitud
from app.qbittorrent import QBittorrentClient
from worker.organization_torrent_guard import verify_organization_torrent_identity
from worker.organization_planner import plan_verified_media

DOWNLOAD_ID = 3
with Session(engine) as session:
    row = session.get(Descarga, DOWNLOAD_ID)
    if row is None:
        raise RuntimeError("DESCARGA_3_NO_EXISTE")
    request = session.get(Solicitud, row.solicitud_id)
    if request is None:
        raise RuntimeError("SOLICITUD_NO_EXISTE")
    if row.estado != "completada" or row.progreso != 1 or row.estado_verificacion != "verificada" or row.organizacion_estado != "pendiente" or row.verificada_en is None:
        raise RuntimeError("DESCARGA_3_NO_APTA")
    print("DESCARGA_3_ESTADO_VERIFICADO=SI")
    print(f"TIPO_SOLICITUD={request.tipo_medio}")
    source_root = Path("/media/descargas_temporales")
    media_root = Path("/media")
    try:
        sources = verify_organization_torrent_identity(
            QBittorrentClient(), row, source_root
        )
    except Exception as exc:
        print(f"ORIGEN_QBITTORRENT_VALIDO=NO;TIPO={type(exc).__name__}")
        raise SystemExit(2) from None
    print("ORIGEN_QBITTORRENT_VALIDO=SI")
    print(f"ORIGEN_ARCHIVOS={len(sources)}")
    try:
        plan = plan_verified_media(row, request, sources, source_root, media_root)
    except Exception as exc:
        print(f"PLAN_BIBLIOTECA_VALIDO=NO;TIPO={type(exc).__name__}")
        raise SystemExit(3) from None
    print("PLAN_BIBLIOTECA_VALIDO=SI")
    print(f"BIBLIOTECA={plan.library}")
    print(f"FICHEROS_PUBLICABLES={len(plan.entries)}")
    print(f"VIDEOS_PUBLICABLES={sum(x.source.suffix.lower() in {'.mkv', '.mp4', '.m4v', '.avi'} for x in plan.entries)}")
    print(f"BYTES_PUBLICABLES={sum(x.size_bytes for x in plan.entries)}")
    print(f"DESTINO_EXISTENTE={any(x.destination.exists() for x in plan.entries)}")
