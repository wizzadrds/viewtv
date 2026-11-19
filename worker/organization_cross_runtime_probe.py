"""Docker prepares a TEST-only Windows staging directory; Windows publishes it.

This module is called only by scripts/test_cross_runtime_windows_publish.ps1.
It NEVER calls powershell.exe from WSL, does not publish the folder, and cannot
access C:/VIEWTV or real qBittorrent, Jellyfin, or SQLite state.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from worker.organization_planner import UnsafeOrganizationPlan

PUBLIC = Path("/mnt/c/Users/Public")
REPO = Path("/home/viewtv/projects/viewtv")
IMAGE = "viewtv:predeploy-0013-dev"
MARKER = "VIEWTV_WINDOWS_SANDBOX_ONLY_V1\n"
STAGE = ".viewtv-stage-1"
TITLE = "Pelicula ficticia (2026)"
VIDEO = TITLE + ".mkv"
SUBTITLE = TITLE + ".es.srt"

DOCKER_STAGE_CODE = r"""
import os
from pathlib import Path
from worker.organization_copy_sandbox import _DIR_FLAGS, _copy_one

root = Path("/scratch")
assert root.is_mount()
assert (root / ".viewtv-win-sandbox-only").read_text() == (
    "VIEWTV_WINDOWS_SANDBOX_ONLY_V1\n"
)
assert not (root / ".viewtv-stage-1").exists()
assert not (root / "Pelicula ficticia (2026)").exists()
os.mkdir(root / ".viewtv-stage-1", mode=0o700)
src_fd = os.open(root / "source", _DIR_FLAGS)
stage_fd = os.open(root / ".viewtv-stage-1", _DIR_FLAGS)
try:
    for name in ("Pelicula ficticia (2026).mkv",
                 "Pelicula ficticia (2026).es.srt"):
        size = (root / "source" / name).stat().st_size
        _copy_one(src_fd, (name,), stage_fd, name, size)
    os.fsync(stage_fd)
finally:
    os.close(src_fd)
    os.close(stage_fd)
print("DOCKER_STAGE_VERIFIED")
"""


def _run(args: list[str], *, timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, check=False, timeout=timeout
    )


def validate_scratch_root(root: Path) -> Path:
    if (
        not isinstance(root, Path)
        or not root.is_absolute()
        or not re.fullmatch(r"viewtv-win-sandbox-[0-9a-f]{32}", root.name)
        or root.parent != PUBLIC
        or not PUBLIC.is_dir()
        or PUBLIC.is_symlink()
        or PUBLIC.resolve(strict=True) != PUBLIC
        or not Path("/mnt/c").is_mount()
        or not root.is_dir()
        or root.is_symlink()
        or root.resolve(strict=True) != root
    ):
        raise UnsafeOrganizationPlan("El sandbox Windows no está autorizado.")

    marker = root / ".viewtv-win-sandbox-only"
    if (
        not marker.is_file()
        or marker.is_symlink()
        or marker.read_text(encoding="utf-8") != MARKER
    ):
        raise UnsafeOrganizationPlan("Marcador de sandbox incorrecto.")
    return root


def prepare_docker_stage(root: Path) -> dict[str, str]:
    root = validate_scratch_root(root)
    source_dir = root / "source"
    if (
        not source_dir.is_dir()
        or source_dir.is_symlink()
        or (root / STAGE).exists()
        or (root / TITLE).exists()
    ):
        raise UnsafeOrganizationPlan("Fuentes o staging de prueba no válidos.")

    files = (VIDEO, SUBTITLE)
    expected = {}
    for name in files:
        src = source_dir / name
        if (
            src.is_symlink()
            or not src.is_file()
            or not 0 < src.stat().st_size <= 32 * 1024 * 1024
        ):
            raise UnsafeOrganizationPlan("Archivo fuente ficticio inválido.")
        expected[name] = hashlib.sha256(src.read_bytes()).hexdigest()

    image = _run(["docker", "image", "inspect", IMAGE], timeout=20)
    if image.returncode:
        raise UnsafeOrganizationPlan("Imagen Docker local 0013 no disponible.")
    command = [
        "docker", "run", "--rm", "--network", "none", "--pull", "never",
        "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--pids-limit=64", "--tmpfs", "/tmp", "--user", "1000:1000",
        "--mount", f"type=bind,source={REPO},target=/src,readonly",
        "--mount", f"type=bind,source={root},target=/scratch",
        "--env", "PYTHONPATH=/src/backend:/src",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--workdir", "/src", "--entrypoint", "python",
        IMAGE, "-c", DOCKER_STAGE_CODE,
    ]
    completed = _run(command, timeout=90)
    if (
        completed.returncode
        or "DOCKER_STAGE_VERIFIED" not in completed.stdout
    ):
        raise UnsafeOrganizationPlan(
            "La preparación Docker no pasó las comprobaciones."
        )

    stage = root / STAGE
    if not stage.is_dir() or stage.is_symlink():
        raise UnsafeOrganizationPlan("Staging no creado de forma segura.")
    for name, digest in expected.items():
        if hashlib.sha256((stage / name).read_bytes()).hexdigest() != digest:
            raise UnsafeOrganizationPlan("El staging no coincide con el origen.")

    return {"docker_staging": "verificado", "archivos": str(len(expected))}


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--stage", type=Path, required=True)
    arguments = cli.parse_args()
    print(json.dumps(prepare_docker_stage(arguments.stage), ensure_ascii=False))
