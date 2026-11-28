"""Cruce SQL de identidades sin revelar nombres ni hashes; solo lectura."""
from app.database import engine
from app.models import Descarga, Medio, Solicitud
from sqlmodel import Session, select

with Session(engine) as db:
    downloads = db.exec(select(Descarga)).all()
    organized = [d for d in downloads if d.organizacion_estado == "organizada"]
    media = db.exec(select(Medio).where(
        Medio.tipo == "pelicula", Medio.disponible_en_jellyfin.is_(True),
    )).all()
    id_by_jf = {m.jellyfin_id for m in media}
    count_direct = 0
    count_tmdb_unique = 0
    count_without_exact = 0
    for download in organized:
        request = db.get(Solicitud, download.solicitud_id)
        if request and request.jellyfin_item_id in id_by_jf:
            count_direct += 1
        elif request and request.tmdb_id is not None and sum(
            m.tmdb_id == request.tmdb_id for m in media
        ) == 1:
            count_tmdb_unique += 1
        else:
            count_without_exact += 1
    print("DESCARGAS_ORGANIZADAS=" + str(len(organized)))
    print("ID_JELLYFIN_EXACTO_EN_SOLICITUD=" + str(count_direct))
    print("ID_TMDB_UNICO_EN_CATALOGO=" + str(count_tmdb_unique))
    print("SIN_VINCULO_ESTRUCTURADO_UNICO=" + str(count_without_exact))
    print("TITULOS_NO_USADOS_PARA_AUTORIZAR=SI")
    print("OPERACIONES_ESCRITURA=0")
