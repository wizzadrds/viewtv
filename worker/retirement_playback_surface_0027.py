"""Auditoría estática 0027 de las tres entradas VIEWTV a Jellyfin.

Sin red y sin reproducir vídeo. Verifica sintaxis de la fuente de FastAPI,
la existencia de autenticación y la expiración HLS. No puede demostrar
qué código carga el contenedor ni si Jellyfin tiene acceso por otra red.
"""
from __future__ import annotations

import ast
from typing import Any


class RutasNoVerificables(ValueError):
    """No completar una auditoría ante rutas o TTL inesperados."""


EXPECTED: dict[str, tuple[str, str]] = {
    "/media/{media_id}/playback-info": ("post", "get_media_playback_info"),
    "/media/{media_id}/stream": ("get", "stream_media"),
    "/media/{media_id}/hls": ("get", "stream_hls"),
}


def _routes(tree: ast.Module) -> dict[str, tuple[str, str, ast.FunctionDef]]:
    routes: dict[str, tuple[str, str, ast.FunctionDef]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            if (
                isinstance(deco, ast.Call)
                and isinstance(deco.func, ast.Attribute)
                and isinstance(deco.func.value, ast.Name)
                and deco.func.value.id == "router"
                and deco.func.attr in ("get", "post")
                and len(deco.args) >= 1
                and isinstance(deco.args[0], ast.Constant)
                and isinstance(deco.args[0].value, str)
            ):
                key = deco.args[0].value
                if key in routes:
                    raise RutasNoVerificables("Ruta duplicada.")
                routes[key] = (deco.func.attr, node.name, node)
    return routes


def _hls_ttl(tree: ast.Module) -> int:
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "HLS_TTL_SECONDS"
                for target in node.targets
            )
        ):
            value = node.value
            if (
                isinstance(value, ast.BinOp)
                and isinstance(value.op, ast.Mult)
                and isinstance(value.left, ast.Constant)
                and type(value.left.value) is int
                and isinstance(value.right, ast.Constant)
                and type(value.right.value) is int
            ):
                return value.left.value * value.right.value
            if isinstance(value, ast.Constant) and type(value.value) is int:
                return value.value
    raise RutasNoVerificables("TTL HLS no verificable.")


def _has_auth(route: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for arg, default in zip(
        route.args.args[-len(route.args.defaults):],
        route.args.defaults,
    ):
        if (
            arg.arg == "_profile"
            and isinstance(default, ast.Call)
            and isinstance(default.func, ast.Name)
            and default.func.id == "Depends"
            and len(default.args) == 1
            and isinstance(default.args[0], ast.Name)
            and default.args[0].id == "get_current_profile"
        ):
            return True
    return False


def auditar_superficie(playback_source: str, hls_source: str) -> dict[str, Any]:
    if (
        not isinstance(playback_source, str)
        or not isinstance(hls_source, str)
        or not 100 <= len(playback_source) <= 150_000
        or not 100 <= len(hls_source) <= 100_000
    ):
        raise RutasNoVerificables("Fuente no verificable.")
    try:
        playback = ast.parse(playback_source)
        hls = ast.parse(hls_source)
    except SyntaxError as exc:
        raise RutasNoVerificables("Código no válido.") from exc
    routes = _routes(playback)
    if not all(
        path in routes and routes[path][:2] == attributes
        and _has_auth(routes[path][2])
        for path, attributes in EXPECTED.items()
    ):
        raise RutasNoVerificables("Falta una ruta protegida o se modificó.")
    ttl = _hls_ttl(hls)
    if ttl < 60 or ttl > 86400:
        raise RutasNoVerificables("TTL HLS fuera de límites.")
    # La auditoría solo identifica una integración real cuando conoce
    # explícitamente una barrera, no deduce seguridad de middleware genérico.
    return {
        "rutas_verificadas": len(EXPECTED),
        "negociacion_protegida_por_perfil": True,
        "stream_directo_protegido_por_perfil": True,
        "hls_protegido_por_perfil": True,
        "ttl_hls_segundos": ttl,
        "control_admision_productivo_0027_instalado": False,
        "streams_jellyfin_directos_fuera_de_viewtv_excluidos": False,
        "autoriza_retirada_fisica": False,
    }
