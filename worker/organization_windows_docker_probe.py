"""Diagnóstico manual de copia Windows DrvFS DENTRO de un Docker desechable.

El contenedor no tiene red, ni montajes de producción, ni .env ni SQLite.
Únicamente puede escribir en /scratch, carpeta temporal bajo C:/Users/Public.
Esta comprobación NO habilita el organizador real.
"""

import json
import subprocess
import tempfile
from pathlib import Path

from worker.organization_drvfs_probe import SCRATCH_PARENT
from worker.organization_planner import UnsafeOrganizationPlan

REPO = Path("/home/viewtv/projects/viewtv")
TEST_IMAGE = "viewtv:predeploy-0013-dev"
MARKER = "VIEWTV_DOCKER_DRVFS_ONLY_V1\n"

# Código ejecutado dentro de un contenedor sin red ni acceso a producción.
CONTAINER_CODE = r"""
import errno
import hashlib
import json
import os
from pathlib import Path

from worker.organization_copy_sandbox import (
    _DIR_FLAGS, _copy_one, _publish_noreplace,
)
from worker.organization_planner import UnsafeOrganizationPlan

root = Path("/scratch")
assert root.is_mount()
assert (root / ".viewtv-docker-test").read_text() == "VIEWTV_DOCKER_DRVFS_ONLY_V1\n"
source = root / "source"
stage = root / "stage"
source.mkdir()
stage.mkdir()
data = b"FICTICIO_TEST_VIEWTV" * (4 * 1024 * 1024 // 19)
(source / "episode.mkv").write_bytes(data)
source_fd = os.open(source, _DIR_FLAGS)
stage_fd = os.open(stage, _DIR_FLAGS)
root_fd = os.open(root, _DIR_FLAGS)
result = {}
try:
    _copy_one(source_fd, ("episode.mkv",), stage_fd,
              "episode.mkv", len(data))
    os.fsync(stage_fd)
    os.link("episode.mkv", "episodio-final.mkv",
            src_dir_fd=stage_fd, dst_dir_fd=root_fd, follow_symlinks=False)
    os.fsync(root_fd)
    assert hashlib.sha256((root / "episodio-final.mkv").read_bytes()).digest() == (
        hashlib.sha256(data).digest()
    )
    assert (source / "episode.mkv").read_bytes() == data
    result["copia_y_hardlink_en_docker"] = "ok"

    (root / "ocupado.mkv").write_bytes(b"ajeno")
    try:
        os.link("episode.mkv", "ocupado.mkv",
                src_dir_fd=stage_fd, dst_dir_fd=root_fd, follow_symlinks=False)
    except FileExistsError:
        result["rechazo_de_sobrescritura"] = "ok"
    else:
        result["rechazo_de_sobrescritura"] = "FALLO"

    os.mkdir("directorio_stage", dir_fd=root_fd)
    try:
        _publish_noreplace(root_fd, "directorio_stage", "directorio_final")
    except (OSError, UnsafeOrganizationPlan) as exc:
        result["renameat2_carpeta"] = "no_soportado_" + str(
            exc.errno if isinstance(exc, OSError) else type(exc).__name__
        )
    else:
        result["renameat2_carpeta"] = "soportado"
finally:
    os.close(source_fd)
    os.close(stage_fd)
    os.close(root_fd)

print(json.dumps(result, ensure_ascii=False))
"""


def probe_container() -> dict:
    if (
        SCRATCH_PARENT.is_symlink()
        or not SCRATCH_PARENT.is_dir()
        or SCRATCH_PARENT.resolve().as_posix() != "/mnt/c/Users/Public"
        or not Path("/mnt/c").is_mount()
    ):
        raise UnsafeOrganizationPlan("El directorio de pruebas no está habilitado.")
    if not REPO.is_dir() or not (REPO / "worker").is_dir():
        raise UnsafeOrganizationPlan("Proyecto VIEWTV no encontrado.")

    # Comprobar existencia de la imagen local sin descargar ninguna otra.
    subprocess.run(
        ["docker", "image", "inspect", TEST_IMAGE],
        check=True, capture_output=True, text=True,
    )

    with tempfile.TemporaryDirectory(
        prefix="viewtv-docker-drvfs-", dir=SCRATCH_PARENT
    ) as temporary:
        root = Path(temporary)
        (root / ".viewtv-docker-test").write_text(MARKER)
        command = [
            "docker", "run", "--rm", "--network", "none", "--pull", "never",
            "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--pids-limit=64", "--tmpfs", "/tmp",
            "--user", "1000:1000",
            "--mount", f"type=bind,source={REPO},target=/src,readonly",
            "--mount", f"type=bind,source={root},target=/scratch",
            "--env", "PYTHONPATH=/src/backend:/src",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--workdir", "/src",
            "--entrypoint", "python",
            TEST_IMAGE, "-c", CONTAINER_CODE,
        ]
        completed = subprocess.run(
            command, check=False, text=True, capture_output=True, timeout=90,
        )
        if completed.returncode != 0:
            # No mostrar toda la salida: podría incluir datos del entorno.
            raise RuntimeError(
                "El contenedor de prueba terminó con error "
                f"{completed.returncode}; consultar diagnóstico privado."
            )
        data = json.loads(completed.stdout.strip().splitlines()[-1])
        if (
            data["copia_y_hardlink_en_docker"] != "ok"
            or data["rechazo_de_sobrescritura"] != "ok"
        ):
            raise UnsafeOrganizationPlan("El mecanismo no pasó la prueba Docker.")
        return data


if __name__ == "__main__":
    print(json.dumps(probe_container(), ensure_ascii=False, indent=2))
