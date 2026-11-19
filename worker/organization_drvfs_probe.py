"""Diagnóstico de operaciones de fichero en Windows DrvFS, solo datos ficticios.

Uso manual, no conectado al worker:
 PYTHONPATH=backend:. python -m worker.organization_drvfs_probe

Crea exclusivamente un directorio aleatorio en C:/Users/Public, lo elimina
al terminar y nunca accede a C:/VIEWTV ni a torrents, medios o credenciales.
El resultado es informativo, no autoriza aún desplegar el organizador.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from worker.organization_copy_sandbox import _DIR_FLAGS, _copy_one, _publish_noreplace
from worker.organization_planner import UnsafeOrganizationPlan

SCRATCH_PARENT = Path("/mnt/c/Users/Public")


def _error(exc: Exception) -> str:
    """Evitar rutas personales y datos de Windows en las salidas."""
    if isinstance(exc, OSError):
        return f"oserror_{exc.errno}"
    return type(exc).__name__


def probe_drvfs() -> dict[str, str]:
    """Prueba únicamente un directorio nuevo bajo el perfil público Windows."""
    if (
        SCRATCH_PARENT.is_symlink()
        or not SCRATCH_PARENT.is_dir()
        or str(SCRATCH_PARENT.resolve()) != "/mnt/c/Users/Public"
    ):
        raise UnsafeOrganizationPlan("Carpeta pública de prueba no disponible.")
    # Limitar el diagnóstico a la unidad C montada por WSL.
    if not Path("/mnt/c").is_mount():
        raise UnsafeOrganizationPlan("No se encontró el montaje de Windows.")

    results: dict[str, str] = {}
    with tempfile.TemporaryDirectory(
        prefix="viewtv-drvfs-probe-", dir=SCRATCH_PARENT
    ) as folder:
        scratch = Path(folder)
        marker = scratch / ".viewtv-drvfs-test"
        marker.write_text("VIEWTV_DRVFS_TEST_ONLY_V1\n", encoding="ascii")
        if marker.is_symlink() or marker.read_text() != "VIEWTV_DRVFS_TEST_ONLY_V1\n":
            raise UnsafeOrganizationPlan("Marcador de prueba inválido.")

        fd = os.open(scratch, _DIR_FLAGS)
        try:
            os.mkdir("staged", dir_fd=fd)
            (scratch / "staged" / "video-test.mkv").write_bytes(b"video ficticio")
            try:
                _publish_noreplace(fd, "staged", "published")
            except (OSError, UnsafeOrganizationPlan) as exc:
                results["publicacion_exclusiva"] = "no_admitida_" + _error(exc)
            else:
                results["publicacion_exclusiva"] = "admitida"
                assert (scratch / "published" / "video-test.mkv").read_bytes() == (
                    b"video ficticio"
                )

            os.mkdir("existente", dir_fd=fd)
            (scratch / "existente" / "preservar.txt").write_text("ajeno")
            os.mkdir("otro_stage", dir_fd=fd)
            try:
                _publish_noreplace(fd, "otro_stage", "existente")
            except UnsafeOrganizationPlan:
                results["no_sobrescritura"] = "proteccion_confirmada"
            except OSError as exc:
                results["no_sobrescritura"] = "no_admitida_" + _error(exc)
            else:
                results["no_sobrescritura"] = "FALLO_DE_SEGURIDAD"
            assert (scratch / "existente" / "preservar.txt").read_text() == "ajeno"

            try:
                os.fsync(fd)
            except OSError as exc:
                results["fsync_directorio"] = "no_admitido_" + _error(exc)
            else:
                results["fsync_directorio"] = "admitido"

            original = scratch / "origen.txt"
            original.write_text("NO MODIFICAR")
            try:
                (scratch / "enlace").symlink_to(original)
            except OSError as exc:
                results["symlink_creacion"] = "no_admitida_" + _error(exc)
            else:
                try:
                    opened = os.open(
                        "enlace", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd,
                    )
                except OSError as exc:
                    results["symlink_nofollow"] = (
                        "proteccion_confirmada_" + _error(exc)
                    )
                else:
                    os.close(opened)
                    results["symlink_nofollow"] = "FALLO_DE_SEGURIDAD"
                assert original.read_text() == "NO MODIFICAR"

            (scratch / "hardlink-origen.mkv").write_bytes(b"contenido de prueba")
            (scratch / "hardlink-ocupado.mkv").write_bytes(b"ajeno")
            try:
                os.link(
                    "hardlink-origen.mkv",
                    "hardlink-nuevo.mkv",
                    src_dir_fd=fd,
                    dst_dir_fd=fd,
                    follow_symlinks=False,
                )
            except OSError as exc:
                results["publicacion_hardlink"] = "no_admitida_" + _error(exc)
            else:
                assert (scratch / "hardlink-nuevo.mkv").read_bytes() == (
                    b"contenido de prueba"
                )
                results["publicacion_hardlink"] = "admitida"

            try:
                os.link(
                    "hardlink-origen.mkv",
                    "hardlink-ocupado.mkv",
                    src_dir_fd=fd,
                    dst_dir_fd=fd,
                    follow_symlinks=False,
                )
            except FileExistsError:
                results["hardlink_no_sobrescritura"] = "proteccion_confirmada"
            except OSError as exc:
                results["hardlink_no_sobrescritura"] = (
                    "no_admitida_" + _error(exc)
                )
            else:
                results["hardlink_no_sobrescritura"] = "FALLO_DE_SEGURIDAD"
            assert (scratch / "hardlink-ocupado.mkv").read_bytes() == b"ajeno"

            # Archivo ficticio de nueve MiB, mayor que un bloque de lectura.
            # Copia por descriptores (fsync + relectura + SHA-256) y
            # publicación de un archivo mediante enlace duro sin reemplazo.
            source_dir = scratch / "prueba-origen"
            stage_dir = scratch / "prueba-stage"
            source_dir.mkdir()
            stage_dir.mkdir()
            test_bytes = b"VIEWTV_FICTICIO_" * (9 * 1024 * 1024 // 16)
            test_file = source_dir / "episodio.mkv"
            test_file.write_bytes(test_bytes)
            from_fd = os.open(source_dir, _DIR_FLAGS)
            stage_fd = os.open(stage_dir, _DIR_FLAGS)
            ticks = [0]

            def progress():
                ticks[0] += 1

            try:
                _copy_one(
                    from_fd,
                    ("episodio.mkv",),
                    stage_fd,
                    "episodio.mkv",
                    len(test_bytes),
                    progress,
                )
                os.fsync(stage_fd)
                os.link(
                    "episodio.mkv", "episodio-publicado.mkv",
                    src_dir_fd=stage_fd,
                    dst_dir_fd=fd,
                    follow_symlinks=False,
                )
                os.fsync(fd)
                copied_hash = hashlib.sha256(
                    (scratch / "episodio-publicado.mkv").read_bytes()
                ).hexdigest()
                original_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
                assert copied_hash == original_hash
                assert ticks[0] >= 2
                results["copia_multi_bloque_windows"] = "confirmada"
            except (OSError, UnsafeOrganizationPlan) as exc:
                results["copia_multi_bloque_windows"] = (
                    "no_admitida_" + _error(exc)
                )
            finally:
                os.close(from_fd)
                os.close(stage_fd)

            (scratch / "Nombre.txt").write_text("primero")
            alternate = scratch / "NOMBRE.txt"
            if alternate.exists():
                results["insensibilidad_mayusculas"] = "detectada"
            else:
                results["insensibilidad_mayusculas"] = "no_detectada"
        finally:
            os.close(fd)

    return results


if __name__ == "__main__":
    result = probe_drvfs()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if (
        result["publicacion_exclusiva"] != "admitida"
        or result["no_sobrescritura"] != "proteccion_confirmada"
        or result["fsync_directorio"] != "admitido"
        or result.get("symlink_nofollow") == "FALLO_DE_SEGURIDAD"
    ):
        print("CONCLUSION: no habilitar publicación en Windows sin adaptación.")
    else:
        print("CONCLUSION: pruebas limitadas de DrvFS superadas; falta Docker.")
