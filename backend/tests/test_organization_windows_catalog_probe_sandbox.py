"""Pruebas del puente Windows -> Jellyfin SOLO con directorios pytest.

La prueba nativa PowerShell cubre NTFS; aquí se prueban invariantes
y el transporte HTTP ficticio sin llamar a Windows ni servicios reales.
"""

import pytest
from worker import organization_windows_catalog_probe_sandbox as bridge
from worker.organization_cross_runtime_probe import STAGE, SUBTITLE, TITLE, VIDEO
from worker.organization_planner import UnsafeOrganizationPlan


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    """Simula únicamente el resultado de validar el marcador Windows."""
    monkeypatch.setattr(bridge, "validate_scratch_root", lambda root: root)
    (tmp_path / STAGE).mkdir()
    (tmp_path / STAGE / VIDEO).write_bytes(b"pelicula-ficticia")
    (tmp_path / STAGE / SUBTITLE).write_bytes(b"subtitulo-ficticio")
    return tmp_path


def _publish(root):
    (root / STAGE).rename(root / TITLE)


def test_before_publication_never_requests_scan(scratch):
    assert bridge.test_catalog_after_windows_publication(scratch, phase="before") == {
        "estado": "pendiente_sin_escaneo",
        "solicitudes_escaneo": 0,
        "catalogo": 0,
    }


def test_after_publication_scans_and_waits_for_indexing(scratch):
    _publish(scratch)
    assert bridge.test_catalog_after_windows_publication(scratch, phase="after") == {
        "estado": "publicacion_windows_catalogo_simulado_ok",
        "solicitudes_escaneo": 1,
        "catalogo_antes": 0,
        "catalogo_antes_finalizar": 0,
        "catalogo_despues": 1,
    }


def test_after_missing_published_directory_fails_closed(scratch):
    with pytest.raises(UnsafeOrganizationPlan, match="no está publicada"):
        bridge.test_catalog_after_windows_publication(scratch, phase="after")


def test_with_stage_and_published_result_is_ambiguous(scratch):
    (scratch / TITLE).mkdir()
    with pytest.raises(UnsafeOrganizationPlan, match="no está publicada"):
        bridge.test_catalog_after_windows_publication(scratch, phase="after")


@pytest.mark.parametrize("removed_name", [VIDEO, SUBTITLE])
def test_incomplete_published_folder_never_requests_scan(scratch, removed_name):
    _publish(scratch)
    (scratch / TITLE / removed_name).unlink()
    with pytest.raises(UnsafeOrganizationPlan, match="incompleta"):
        bridge.test_catalog_after_windows_publication(scratch, phase="after")


def test_extra_file_never_requests_scan(scratch):
    _publish(scratch)
    (scratch / TITLE / "otro.txt").write_text("no admitido")
    with pytest.raises(UnsafeOrganizationPlan, match="incompleta"):
        bridge.test_catalog_after_windows_publication(scratch, phase="after")


def test_symlink_inside_folder_never_requests_scan(scratch):
    _publish(scratch)
    (scratch / TITLE / VIDEO).unlink()
    (scratch / TITLE / VIDEO).symlink_to(scratch / TITLE / SUBTITLE)
    with pytest.raises(UnsafeOrganizationPlan, match="no validable"):
        bridge.test_catalog_after_windows_publication(scratch, phase="after")


@pytest.mark.parametrize("phase", ["", "production", "BEFORE", "after/../"])
def test_invalid_phase_is_rejected(scratch, phase):
    with pytest.raises(ValueError, match="Fase"):
        bridge.test_catalog_after_windows_publication(scratch, phase=phase)


def test_real_validator_always_rejects_generic_pytest_root(tmp_path):
    with pytest.raises(UnsafeOrganizationPlan):
        bridge.test_catalog_after_windows_publication(tmp_path, phase="before")
