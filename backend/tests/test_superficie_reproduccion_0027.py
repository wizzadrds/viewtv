"""0027: rutas de reproducción y alcance real del prototipo de admisión.

La auditoría NO autoriza detener clientes Jellyfin ni eliminar películas.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from worker.retirement_playback_surface_0027 import (
    RutasNoVerificables,
    auditar_superficie,
)

ROOT = Path(__file__).resolve().parents[2]
PLAYBACK = (ROOT / "backend/app/jellyfin_playback.py").read_text(encoding="utf-8")
HLS = (ROOT / "backend/app/jellyfin_hls.py").read_text(encoding="utf-8")
SCRIPT = ROOT / "scripts/viewtv_retirada_superficie_reproduccion_0027.py"
SPEC = importlib.util.spec_from_file_location("playback_surface_0027", SCRIPT)
assert SPEC and SPEC.loader
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


def test_tres_rutas_de_viewtv_no_son_un_bloqueo_real():
    out = auditar_superficie(PLAYBACK, HLS)
    assert out == {
        "rutas_verificadas": 3,
        "negociacion_protegida_por_perfil": True,
        "stream_directo_protegido_por_perfil": True,
        "hls_protegido_por_perfil": True,
        "ttl_hls_segundos": 14400,
        "control_admision_productivo_0027_instalado": False,
        "streams_jellyfin_directos_fuera_de_viewtv_excluidos": False,
        "autoriza_retirada_fisica": False,
    }


@pytest.mark.parametrize("needle", [
    '@router.post("/media/{media_id}/playback-info")',
    '@router.get("/media/{media_id}/stream")',
    '@router.get("/media/{media_id}/hls")',
])
def test_si_una_ruta_desaparece_la_auditoria_bloquea(needle):
    assert needle in PLAYBACK
    with pytest.raises(RutasNoVerificables):
        auditar_superficie(PLAYBACK.replace(needle, ""), HLS)


def test_si_un_stream_pierde_autenticacion_no_se_infiere_seguridad():
    altered = PLAYBACK.replace(
        "_profile: Perfil = Depends(get_current_profile)",
        "_profile: Perfil = None",
        1,
    )
    assert altered != PLAYBACK
    with pytest.raises(RutasNoVerificables):
        auditar_superficie(altered, HLS)


@pytest.mark.parametrize("replacement", ["0", "90000", '"cuatro horas"'])
def test_ttl_imprevisto_falla_cerrado(replacement):
    modified = HLS.replace("HLS_TTL_SECONDS = 4 * 3600", "HLS_TTL_SECONDS = " + replacement)
    assert modified != HLS
    with pytest.raises(RutasNoVerificables):
        auditar_superficie(PLAYBACK, modified)


def test_puerto_jellyfin_loopback_no_demuestra_exclusion_global(monkeypatch, capsys):
    commands = []

    def fake_run(args, **kwargs):
        commands.append((args, kwargs))
        return SimpleNamespace(
            returncode=0, stdout="8096/tcp -> 127.0.0.1:8097\n", stderr="",
        )

    monkeypatch.setattr(RUN.subprocess, "run", fake_run)
    assert RUN.main() == 0
    output = capsys.readouterr().out
    assert "RUTAS_AUTENTICADAS_CONTADAS=3" in output
    assert "TTL_HLS_SEGUNDOS=14400" in output
    assert "PUERTO_JELLYFIN_PUBLICADO_SOLO_LOOPBACK=SI" in output
    assert "OTROS_ACCESOS_JELLYFIN_DESCARTADOS=NO" in output
    assert "BLOQUEO_REAL_DE_NUEVOS_STREAMS=NO" in output
    assert "PERMISO_BORRADO_FISICO=NO" in output
    assert commands[0][0] == ["docker", "port", "viewtv-jellyfin"]
    assert commands[0][1]["timeout"] == 15
    assert commands[0][1]["capture_output"] is True


@pytest.mark.parametrize("port_output", [
    "8096/tcp -> 0.0.0.0:8097\n",
    "8096/tcp -> 192.168.1.20:8097\n",
    "8096/tcp -> 127.0.0.1:8097\n8096/tcp -> 0.0.0.0:8097\n",
    "8096/tcp -> 127.0.0.1:8097\nAPI_KEY=secret\n",
    "",
])
def test_puerto_publico_o_incierto_no_se_declara_seguro(port_output, monkeypatch, capsys):
    monkeypatch.setattr(
        RUN.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=port_output, stderr="PRIVATE_TOKEN",
        ),
    )
    assert RUN.main() == 2
    output = capsys.readouterr().out
    assert "BLOQUEADA_DATOS_NO_CONFIABLES" in output
    assert "PRIVATE_TOKEN" not in output
    assert "PERMISO_BORRADO_FISICO=NO" in output


def test_no_lee_claves_ni_modifica_contenedores():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "docker\", \"port\", \"viewtv-jellyfin" in source
    for forbidden in (
        "docker exec", "docker stop", "docker restart",
        "torrents_pause", "torrents_delete", "session.commit(",
        "os.remove(", "unlink(",
    ):
        assert forbidden not in source


def test_no_autoriza_retiro_con_link_hls_valido():
    out = auditar_superficie(PLAYBACK, HLS)
    assert out["ttl_hls_segundos"] > 0
    assert out["autoriza_retirada_fisica"] is False
    assert out["streams_jellyfin_directos_fuera_de_viewtv_excluidos"] is False
