"""Contrato del mutex Windows 0022 sin consultar servicios reales.

Las pruebas ejecutables sobre procesos y NTFS viven en los sandboxes .ps1;
estos tests bloquean cambios accidentales que omitan el protocolo.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCK = (ROOT / "scripts/viewtv_windows_media_lock_0022.ps1").read_text(encoding="utf-8")
PUB = (ROOT / "scripts/viewtv_windows_publicador_0013.ps1").read_text(encoding="utf-8")
AUD = (ROOT / "scripts/viewtv_windows_retirada_mutex_auditoria_0022.ps1").read_text(
    encoding="utf-8"
)
SANDBOX = (ROOT / "scripts/viewtv_windows_media_lock_sandbox_0022.ps1").read_text(
    encoding="utf-8"
)
MOCK = (ROOT / "scripts/viewtv_windows_publicador_lock_mock_sandbox_0022.ps1").read_text(
    encoding="utf-8"
)


def test_unico_nombre_productivo_global_para_publicacion_y_retirada():
    assert "Global\\VIEWTV-MEDIA-EXCLUSIVA-PUBLICACION-RETIRADA-0022" in LOCK
    assert "Enter-ViewtvMediaExclusion0022" in PUB
    assert "Enter-ViewtvMediaExclusion0022" in AUD
    assert "-Proposito 'publicador'" in PUB
    assert "-Proposito 'retirada'" in AUD


def test_mutex_global_no_cambia_nombre_por_parametro_de_usuario():
    assert "$SandboxId -ne ''" in LOCK
    assert "No se admiten variantes" in LOCK
    assert "^[a-f0-9]{32}$" in LOCK
    assert "Global\\VIEWTV-MEDIA-SANDBOX-0022-" in LOCK


def test_adquisicion_no_espera_ni_silencia_un_mutex_ocupado():
    assert "$mutex.WaitOne(0)" in LOCK
    assert "if (-not $owned)" in LOCK
    assert "throw 'Otro proceso ocupa" in LOCK
    assert "AbandonedMutexException" in LOCK
    assert "Mutex abandonado" in LOCK


def test_liberacion_explicitamente_en_finally_del_publicador():
    source = PUB.split("function Process-One {", 1)[1].split(
        "function Assert-AuthorityReady", 1
    )[0]
    lock_position = source.index("Enter-ViewtvMediaExclusion0022")
    policy_position = source.index("Get-ViewtvPolicy")
    claim_position = source.index("Invoke-ViewtvAuthority 'claim'")
    assert lock_position < policy_position < claim_position
    assert "finally {" in source
    assert source.index("Exit-ViewtvMediaExclusion0022") > claim_position
    assert "viewtv_windows_media_lock_0022.ps1" in source


def test_sin_biblioteca_de_mutex_no_puede_reclamar_trabajos():
    source = PUB.split("function Process-One {", 1)[1].split(
        "function Assert-AuthorityReady", 1
    )[0]
    assert "if(-not [IO.File]::Exists($guardLibrary))" in source
    assert "throw 'Falta protocolo de exclusion 0022" in source
    assert source.index("throw 'Falta protocolo") < source.index("Invoke-ViewtvAuthority 'claim'")


def test_errores_no_deben_ser_convertidos_en_autorizacion():
    assert "$mutex.ReleaseMutex()" in LOCK
    assert "$mutex.Dispose()" in LOCK
    assert "if ($LASTEXITCODE" not in AUD
    assert "RETIRADA_0022_AUTORIZA_ELIMINACION=NO" in AUD
    assert "RETIRADA_0022_BLOQUEO_QBIT_Y_STREAMS=NO" in AUD


@pytest.mark.parametrize(
    "dangerous",
    ["Remove-Item", "rmdir", "qbit.torrents_delete", "Stop-Torrent", "DELETE FROM"],
)
def test_auditoria_compartida_no_es_ejecutor_destrucivo(dangerous):
    assert dangerous not in AUD


def test_publicador_en_mode_library_no_publica():
    assert "if ($Mode -ceq 'Library')" in PUB
    assert "return\n} elseif ($Mode -ceq 'Preflight')" in PUB


def test_sandbox_windows_separa_nombre_y_solo_mata_su_subproceso():
    assert "-Proposito 'sandbox' -SandboxId $RunId" in SANDBOX
    assert "Start-Process -FilePath $exe" in SANDBOX
    assert "Stop-Process -Id $child.Id" in SANDBOX
    assert "ARCHIVOS_MEDIOS_REALES_TOCADOS=0" in SANDBOX


def test_mocks_no_consumen_trabajos_reales():
    assert ". $publisher -Mode Library" in MOCK
    assert "function Get-ViewtvPolicy" in MOCK
    assert "function Invoke-ViewtvAuthority" in MOCK
    assert "PUBLICACION_REAL_Y_CLAIMS=0" in MOCK


def test_bloqueo_cooperativo_no_afirma_sincronizar_qbit_y_jellyfin():
    assert "RETIRADA_0022_PUBLICADOR_PRODUCCION_INTEGRADO=NO_VERIFICADO" in AUD
    assert "RETIRADA_0022_BLOQUEO_QBIT_Y_STREAMS=NO" in AUD
    assert "RETIRADA_0022_ARCHIVOS_ELIMINADOS=0" in AUD
