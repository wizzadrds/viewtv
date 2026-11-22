"""Diagnóstico SOLO LECTURA de diarios propietarios, sin títulos ni rutas en stdout."""
import json
from pathlib import Path

root = Path("/mnt/c/VIEWTV/media")
for file in sorted(Path("/mnt/c/VIEWTV/publicador/journal").glob("download-*.json")):
    record = json.loads(file.read_text(encoding="utf8"))
    intent = record.get("intent") or {}
    sources = []
    targets = []
    for entry in intent.get("files", []):
        src = root / "descargas_temporales" / entry["source_relative"]
        target = root / entry["destination_relative"]
        sources.append(src)
        targets.append(target)
    print("DESCARGA_ID=" + str(record["download_id"]))
    print("ORIGEN_ARCHIVOS_PRESENTES=" + str(sum(p.is_file() for p in sources)))
    print("ORIGEN_PARENTES_PRESENTES=" + str(sum(p.parent.is_dir() for p in sources)))
    print("PUBLICADOS_PRESENTES=" + str(sum(p.is_file() for p in targets)))
    print("PUBLICADOS_PARENTES_PRESENTES=" + str(sum(p.parent.is_dir() for p in targets)))
    print("ARCHIVOS_MANIFIESTO=" + str(len(sources)))
    print("CARPETA_DIARIO_EQUIVALENTE=" + str(
        all(path.parent.name == record.get("folder") for path in targets)
    ))
    folder = root / "Peliculas" / str(record.get("folder"))
    print("CARPETA_DIARIO_PRESENTE=" + str(folder.is_dir()))
    print("ORIGEN_RAIZ_PRESENTE=" + str((root / "descargas_temporales").is_dir()))
