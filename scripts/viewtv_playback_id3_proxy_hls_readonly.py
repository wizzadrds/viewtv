"""Prueba privada de cadena real API FastAPI HLS para ID3, sin sesiones ni secretos.
TestClient reemplaza SOLO la dependencia de autenticación en memoria local.
"""
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.database import engine
from app.models import Descarga, Solicitud, Medio
from app.auth import get_current_profile
from app.main import app

def choose():
    with Session(engine) as s:
        download=s.get(Descarga,3)
        request=s.get(Solicitud,download.solicitud_id)
        matches=[m for m in s.exec(select(Medio)).all()
                 if m.titulo.strip().casefold()==request.titulo.strip().casefold()]
        if len(matches)!=1: raise RuntimeError("MEDIO_NO_UNICO")
        return matches[0].id

def urls(body):
    return [l.strip() for l in body.splitlines() if l.strip() and not l.startswith("#")]
def local_url(url):
    parsed=urlsplit(url)
    path=parsed.path
    if path.startswith("/api/viewtv/"):
        path=path[len("/api/viewtv"):]
    if not path.startswith("/jellyfin/media/"): raise RuntimeError("URL_HLS_NO_LOCAL")
    return path+("?"+parsed.query if parsed.query else "")
media_id=choose()
app.dependency_overrides[get_current_profile]=lambda: object()
try:
    with TestClient(app) as client:
        reply=client.post(f"/jellyfin/media/{media_id}/playback-info")
        print(f"NEGOCIACION_HTTP={reply.status_code}",flush=True)
        reply.raise_for_status()
        sources=reply.json().get("fuentes") or []
        media=[a for a in sources if a.get("modo")=="hls" and a.get("url")]
        if len(media)!=1: raise RuntimeError("FUENTE_HLS_NO_UNICA")
        m=client.get(local_url(media[0]["url"]))
        print(f"PROXY_MASTER_HTTP={m.status_code} TYPE={m.headers.get('content-type','').split(';')[0]} VALIDA={m.content.startswith(b'#EXTM3U')}",flush=True)
        m.raise_for_status()
        branches=urls(m.text)
        print(f"PROXY_MASTER_ENTRADAS={len(branches)}",flush=True)
        if not branches: raise RuntimeError("MASTER_SIN_VARIANTE")
        v=client.get(local_url(branches[0]))
        print(f"PROXY_VARIANTE_HTTP={v.status_code} TYPE={v.headers.get('content-type','').split(';')[0]} VALIDA={v.content.startswith(b'#EXTM3U')} BYTES={len(v.content)}",flush=True)
        v.raise_for_status()
        segments=urls(v.text)
        print(f"PROXY_VARIANTE_SEGMENTOS={len(segments)}",flush=True)
        if not segments: raise RuntimeError("VARIANTE_SIN_SEGMENTOS")
        s=client.get(local_url(segments[0]))
        print(f"PROXY_PRIMER_FRAGMENTO_HTTP={s.status_code} TYPE={s.headers.get('content-type','').split(';')[0]} BYTES={len(s.content)}",flush=True)
        s.raise_for_status()
        print("API_HLS_ID3_CADENA_COMPLETA=SI",flush=True)
except Exception as exc:
    print(f"API_HLS_ERROR_TIPO={type(exc).__name__}",flush=True)
finally:
    app.dependency_overrides.clear()
