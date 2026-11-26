"""Preflight INTEGRADO, exclusivamente GET/lectura, de retiradas de ViewTV.

Procesa localmente dos fuentes: Python dentro de la API (SQL+Jellyfin+qBit)
y auditoría nativa NTFS de Windows. Nunca ejecuta POST ni DELETE.
No muestra nombres, ubicaciones, hashes, PINs ni datos de perfiles.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker.retirement_preflight_0018 import evaluar_retiradas  # noqa: E402

JOURNALS = Path("/mnt/c/VIEWTV/publicador/journal")
PATTERN = re.compile(r"download-([1-9][0-9]*)\.json\Z")
MAX_JOURNALS = 500


def _cmd(command: list[str], *, source: str | None = None) -> str:
    try:
        p = subprocess.run(
            command,
            input=source, text=True,
            capture_output=True, check=False, timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Consulta de evidencias no disponible.") from exc
    if p.returncode != 0 or not p.stdout:
        raise RuntimeError("Una fuente de evidencia no pudo verificarse.")
    return p.stdout.lstrip("\ufeff").strip()


def _api_snapshot() -> dict:
    source = (ROOT / "scripts/viewtv_retirada_snapshot_api_0018.py").read_text(
        encoding="utf-8",
    )
    output = _cmd(["docker", "exec", "-i", "viewtv-api-1", "python", "-"], source=source)
    data = json.loads(output)
    if not isinstance(data, dict):
        raise ValueError("Instantánea SQL/Jellyfin/qBit no válida.")
    return data


def _evidence_windows() -> list[dict]:
    source = ROOT / "scripts/viewtv_windows_retirada_inventario_0018.ps1"
    ps_path = "\\\\wsl.localhost\\Ubuntu-24.04" + str(source).replace("/", "\\")
    response = _cmd([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", ps_path,
    ])
    evidence = json.loads(response)
    if (
        not isinstance(evidence, dict)
        or evidence.get("version") != 1
        or evidence.get("modo") != "solo_lectura"
        or evidence.get("retiradas_ejecutadas") != 0
        or evidence.get("originales_modificados") != 0
        or not isinstance(evidence.get("evidencias"), list)
    ):
        raise ValueError("Auditoría NTFS sin garantía de solo lectura.")
    return evidence["evidencias"]


def _journals_readonly() -> dict[int, tuple[dict, str]]:
    info = JOURNALS.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("Diarios privados no disponibles.")
    files = list(JOURNALS.glob("download-*.json"))
    if len(files) > MAX_JOURNALS:
        raise ValueError("Demasiados diarios para una lectura limitada.")
    journals: dict[int, tuple[dict, str]] = {}
    for path in files:
        match = PATTERN.fullmatch(path.name)
        if match is None:
            raise ValueError("Diario con nombre inesperado.")
        download_id = int(match.group(1))
        handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            entry = os.fstat(handle)
            if not stat.S_ISREG(entry.st_mode) or not 30 <= entry.st_size <= 16384:
                raise ValueError("Diario irregular.")
            payload = os.read(handle, 16385)
            if len(payload) != entry.st_size:
                raise ValueError("Diario cambió durante su lectura.")
        finally:
            os.close(handle)
        record = json.loads(payload)
        if not isinstance(record, dict) or record.get("download_id") != download_id:
            raise ValueError("Diario no corresponde a su ID.")
        journals[download_id] = (
            record,
            hashlib.sha256(payload).hexdigest(),
        )
    return journals


def main() -> int:
    try:
        before = _evidence_windows()
        snapshot = _api_snapshot()
        journals = _journals_readonly()
        after = _evidence_windows()
        # Nunca aceptar un preflight si los diarios cambiaron mientras
        # qBit/Jellyfin estaban respondiendo.
        if before != after:
            raise ValueError("Evidencia NTFS cambió durante el preflight.")
        approved_ids = {
            item["download_id"]
            for item in after if isinstance(item, dict)
            and item.get("ntfs_verified") is True
        }
        if approved_ids - journals.keys():
            raise ValueError("Prueba Windows sin diario local comparable.")
        result = evaluar_retiradas(snapshot, journals, after)
        reasons = Counter(r for item in result for r in item["motivos"])
        print("PREFLIGHT_0018=REALIZADO_SOLO_LECTURA")
        print("PELICULAS_ANALIZADAS=" + str(len(result)))
        print("DIARIOS_NTFS_VERIFICADOS=" + str(len(approved_ids)))
        print("DIARIOS_VERIFICADOS_EN_SNAPSHOT=" + str(len(journals)))
        print("PELICULAS_BLOQUEADAS=" + str(sum(
            row["estado"] == "bloqueada" for row in result
        )))
        print("PERMISO_DE_BORRADO_OTORGADO=NO")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        for reason, total in sorted(reasons.items()):
            print("MOTIVO_" + reason.upper() + "=" + str(total))
        for row in result:
            print("MEDIO_" + str(row["medio_id"]) + "=BLOQUEADA")
        return 0
    except (RuntimeError, ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
        print("PREFLIGHT_0018=BLOQUEADO")
        print("CAUSA=FUENTES_INCONSISTENTES_O_NO_DISPONIBLES")
        print("ARCHIVOS_ELIMINADOS=0")
        print("TORRENTS_MODIFICADOS=0")
        # Los detalles pueden incluir rutas y credenciales; no mostrarlos.
        _ = exc
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
