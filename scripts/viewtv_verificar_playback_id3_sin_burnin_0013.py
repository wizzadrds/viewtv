"""Postdespliegue read-only. Prueba fuente 3 y control sin revelar credenciales."""
from urllib.parse import parse_qs,urlsplit
from sqlmodel import Session,select
from app.database import engine
from app.models import Descarga,Solicitud,Medio
from app.jellyfin_playback import JellyfinPlaybackClient

with Session(engine) as s:
    d=s.get(Descarga,3);q=s.get(Solicitud,d.solicitud_id)
    media=s.exec(select(Medio)).all()
    new=[m for m in media if m.titulo.strip().casefold()==q.titulo.strip().casefold()]
    control=[m for m in media if 'nadie 2' in m.titulo.strip().casefold()]
    if len(new)!=1 or len(control)!=1: raise RuntimeError("METADATA_NO_EXCLUSIVA")
    chosen=[("ID3",new[0]),("CONTROL",control[0])]
for label,m in chosen:
    result=JellyfinPlaybackClient().playback_info(m.jellyfin_id)
    sources=result.get("MediaSources") or []
    if len(sources)!=1:raise RuntimeError("FUENTE_NO_EXCLUSIVA")
    src=sources[0]
    url=src.get("TranscodingUrl") or ""
    qs={k.casefold():v for k,v in parse_qs(urlsplit(url).query).items()}
    indexes=qs.get("subtitlestreamindex",[])
    print(f"CASO={label}")
    print(f"HLS_DISPONIBLE={src.get('SupportsTranscoding') is True and urlsplit(url).path.lower().endswith('.m3u8')}")
    print(f"SUBTITULO_INCRUSTADO_POR_DEFECTO={any(x.isdecimal() for x in indexes)}")
    if label=="ID3" and any(x.isdecimal() for x in indexes):
        raise RuntimeError("CONTINUA_INCRUSTANDO_SUBTITULO")
print("HLS_NEGOCIACION_0013_SIN_BURNIN=OK")
