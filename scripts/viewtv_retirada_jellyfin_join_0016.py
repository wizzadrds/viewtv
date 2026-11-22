"""Cruce read-only de la ruta real Jellyfin con el journal NTFS protegido.

Las rutas, títulos e IDs de Jellyfin viajan SOLO en memoria de procesos
locales. stdout revela únicamente recuentos, nunca claves ni nombres.
"""
import json
import subprocess
from pathlib import Path, PurePosixPath

QUERY = """
import json
from sqlmodel import Session, select
from app.database import engine
from app.jellyfin import JellyfinClient, JellyfinError
from app.models import Medio

result = []
with Session(engine) as db:
    movies = db.exec(select(Medio).where(
        Medio.tipo == 'pelicula', Medio.disponible_en_jellyfin.is_(True)
    )).all()
try:
    client = JellyfinClient()
    items = []
    for offset in range(0, 10_000, 100):
        page = client._get('/Items', {
            'Recursive': 'true',
            'IncludeItemTypes': 'Movie',
            'Fields': 'Path',
            'StartIndex': offset,
            'Limit': 100,
        })
        chunk = page.get('Items', [])
        total = page.get('TotalRecordCount')
        assert isinstance(chunk, list) and all(
            isinstance(row, dict) for row in chunk
        )
        assert isinstance(total, int) and 0 <= total <= 10_000
        items.extend(chunk)
        if len(items) >= total:
            break
        assert len(chunk) == 100
    else:
        raise ValueError('Límite de paginación excedido')
except (JellyfinError, ValueError, TypeError, AssertionError):
    items = []
for movie in movies:
    matching = [
        row for row in items
        if isinstance(row, dict) and row.get('Id') == movie.jellyfin_id
        and row.get('Type') == 'Movie'
    ]
    path = matching[0].get('Path') if len(matching) == 1 else None
    result.append({
        'id': movie.jellyfin_id,
        'path': path,
        'reason': (
            'correcto' if isinstance(path, str) and path
            else 'tipo_o_identidad' if len(matching) != 1 else 'sin_ruta'
        ),
    })
print(json.dumps(result))
"""

command = subprocess.run(
    ["docker", "exec", "-i", "viewtv-api-1", "python", "-"],
    input=QUERY, capture_output=True, text=True, timeout=60, check=False,
)
if command.returncode != 0:
    raise SystemExit("JELLYFIN_CRUCE=NO_DISPONIBLE")
try:
    movies = json.loads(command.stdout)
except (ValueError, TypeError):
    raise SystemExit("JELLYFIN_CRUCE=NO_INTERPRETABLE") from None

root = Path("/mnt/c/VIEWTV/publicador/journal")
journal_files = sorted(root.glob("download-*.json"))
paths = []
for journal in journal_files:
    record = json.loads(journal.read_text(encoding="utf-8"))
    entry_paths = [
        "/" + str(f["destination_relative"]).lstrip("/")
        for f in record.get("intent", {}).get("files", [])
        if str(f.get("destination_relative", "")).lower().endswith(
            (".mkv", ".mp4", ".m4v", ".avi")
        )
    ]
    if len(entry_paths) == 1:
        paths.append((record["download_id"], "/media" + entry_paths[0]))
print("PELICULAS_JELLYFIN_CATALOGO=" + str(len(movies)))
for reason in ('consulta_fallida', 'tipo_o_identidad', 'sin_ruta', 'correcto'):
    print("JELLYFIN_" + reason.upper() + "=" + str(sum(
        row.get('reason') == reason for row in movies
    )))
print("JELLYFIN_PATH_MOVIE_PRESENTE=" + str(sum(
    isinstance(row.get("path"), str) for row in movies
)))
match_counts = []
for _, location in paths:
    path = PurePosixPath(location)
    if not path.is_relative_to(PurePosixPath("/media/Peliculas")):
        match_counts.append(0)
        continue
    matched = sum(
        isinstance(row.get("path"), str)
        and PurePosixPath(row["path"]) == path
        for row in movies
    )
    match_counts.append(matched)

print("DIARIOS_CON_VIDEO_UNICO=" + str(len(paths)))
print("JOURNAL_JELLYFIN_PATH_EXACTO_UNICO=" + str(
    sum(n == 1 for n in match_counts)
))
print("JOURNAL_JELLYFIN_NO_UNICO_O_AUSENTE=" + str(
    sum(n != 1 for n in match_counts)
))
print("RETIRADA_AUTOMATICA_HABILITADA=NO")
print("OPERACIONES_ESCRITURA=0")
