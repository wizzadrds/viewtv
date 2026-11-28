# VIEWTV 0035 — cerrar gate global Ruff sin modificar contratos de retirada

**Fecha:** 28/11/2026. **Rama autorizada:** `viewtv-seguimiento-descargas-0012`; PR #2 permanece OPEN/DRAFT y no se fusiona. **Ámbito:** únicamente fuente Python/versionado y documentación de calidad. **Sin despliegue**, sin acceso destructivo a películas, torrents, cachés, firewall, ACL ni servicios.

## Contexto y copia de seguridad

Los hitos 0030–0034 documentaron **128 incidencias Ruff** en código histórico fuera de los módulos nuevos. En 0035 se ha corregido la deuda como gate previo a un futuro despliegue, sin confundir aprobación de lint con seguridad operativa de una retirada.

Antes de la modificación se archivaron los **267 archivos Python versionados** de `backend/`, `worker/` y `scripts/` en un respaldo privado fuera del repositorio:
`/home/viewtv/viewtv-backups/0035-20261128/ruff_python_before.tar.gz`. SHA-256:
`13c721efac07badd49335afacc3e8273fff47801b8bead8e94a34d1ea072cce4`.
El script de revisión de cambios de texto con comprobación exacta y AST también está **fuera del repo**, en `/home/viewtv/viewtv-backups/0035-20261128/fix_ruff_0035.py`. No se suben esos respaldos ni información de los medios a GitHub.

## Correcciones

1. Aplicación local con Ruff v0.17.6 en contenedor de pruebas sin red, usuario WSL no privilegiado y worktree autorizado: `ruff check --fix --no-cache backend worker scripts` con reglas del repositorio **sin relajarlas**. Principalmente imports en orden, imports sin usar, `noqa` que ya no corresponden a reglas activas, `datetime.UTC` y cambios de estilo mecánicos.
2. Segunda pasada **de sustituciones revisadas y AST válido** en 14 ficheros para los avisos restantes: formato de líneas de migraciones y tests, combinación de contextos `with`, argumentos explícitos de `subprocess.run`, y excepciones de diagnósticos que intencionadamente no deben exponer secretos ni rutas.
3. En `worker/retirement_preflight_0018.py`, `worker/retirement_inventory_0020.py` y el orquestador del preflight se mantienen las **`ValueError` públicas que los llamantes ya capturan**. Ruff prefería `TypeError` en comprobaciones de tipo; cambiar la clase habría modificado la semántica del fallo cerrado. Las excepciones locales llevan un `# noqa: TRY004` justificado e individual, no un `ignore` global. Lo mismo ocurre con capturas amplias localmente justificadas en límites de privacidad de scripts puntuales, no en rutas nuevas de borrado.
4. Se revisaron diffs de migraciones, rutas críticas de retirada, worker, herramientas de diagnóstico y cliente torrent; no se añadieron endpoints de eliminación ni acciones sobre servicios reales. No se alteraron formatos de diarios NTFS, claves, ni reglas del firewall.

## Calidad verificada

- **Ruff global:** `ruff check --no-cache --output-format concise backend worker scripts` → **All checks passed!**, 0 avisos. El análisis se efectuó sobre los ficheros montados solo lectura en un contenedor offline.
- `git diff --check`: PASS.
- El conjunto de cambios alcanza 76 ficheros Python históricos, con predominio de ordenación de imports y formato; el respaldo anterior permite comparar o revertir.
- **Regresión completa backend: 1572/1572 PASS** (dos advertencias de dependencias Starlette/FastAPI), ejecutada sin red y con código montado solo lectura. **TypeScript PASS, ESLint PASS, smoke real 10/10 PASS**.
- **Preflight real de retirada 0018 tras los cambios:** 4/4 películas BLOQUEADAS, 2/2 diarios NTFS verificados, `PERMISO_DE_BORRADO_OTORGADO=NO`, cero archivos eliminados y cero torrents modificados. Los tipos de error de las rutas de denegación se mantuvieron intencionalmente.

## Lo que NO resuelve este hito

Eliminar fallos de lint **NO autoriza películas ni corrige automáticamente las barreras funcionales**. El 0034 demostró que Windows admite un nuevo `CreateHardLinkW` a pesar de `FileShare.None` y de dos handles de borrado. Además Jellyfin y qBit nativos comparten SID con la sesión Windows observada; hay puertos externos y reglas permisivas; HLS v2 y el ASGI guard sólo están probados en TestClient, y las cuatro películas reales siguen sin aprobación administrativa.

Para terminar de verdad hacen falta identidades Windows efectivamente segregadas (broker privilegiado/lectores limitados), ACL nativas probadas contra un tercer link desde otro SID, custodia completa de **un torrent exacto**, control de acceso LAN/Jellyfin, despliegue transaccional HLS v2 en todos los modos, consumo HMAC administrativo por película, diario durable y recuperación tras kill/reinicio, validación de espacio recuperado, y aprobación expresa para la primera película. **Cualquier prueba negativa mantiene el borrado bloqueado.**
