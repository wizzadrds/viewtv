# VIEWTV — panel Descargas sin botón manual

**Fecha:** 20-11-2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
Hito práctico del [plan de salida rápida](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Necesidad del usuario y funcionamiento observado

El usuario pidió quitar el botón «↻ Actualizar» de «Mis descargas», ya que
el estado debería actualizarse automáticamente.

Al revisar `frontend/components/downloads-panel.tsx` se verificó que
**ya existía** una consulta GET periódica a
`/solicitudes/descargas?limit=20&offset=...` **cada 15 segundos**
mientras `document.visibilityState === "visible"`. También se
cargaba al entrar y al cambiar de página. El botón adicional
provocaba otra consulta innecesaria mediante `refreshIndex`.

## Cambio aplicado

- Se elimina el botón «↻ Actualizar» y el estado
  `refreshIndex`; queda el mensaje «Se actualiza automáticamente».
- Se conserva `setInterval` de **15 segundos** solo en la
  vista activa y visible.
- Se añade un `visibilitychange` que consulta de inmediato
  al volver a la pestaña, sin esperar los 15 segundos.
- Se da de baja el listener y el intervalo al salir de la
  vista, además de cancelar `AbortController`. Se conserva
  la protección contra respuestas antiguas `latestRequest`.
- Quedan intactos el tratamiento de errores y sesiones 401,
  los estados, la barra de progreso y la paginación.
- Este cambio **solo consulta datos**: no inicia, reanuda ni
  modifica torrents; tampoco toca SQLite o la biblioteca.

Se añadió `frontend/tests/downloads-panel-refresh.test.mjs` como
**comprobación de contrato del código** con Node `node:test`.
Estas pruebas son estáticas; no sustituyen la verificación
de una descarga real en el navegador. Comprueban periodicidad,
refresco al volver, ausencia del botón y preservación de las
salvaguardas de error/cancelación/paginación.

## Pruebas previas

- **4/4 pruebas Node correctas**, en contenedor sin red, fuente
  montada solo lectura, exit code 0.
- Compilación optimizada **Next.js 15.5.28: correcta**,
  incluyendo lint, TypeScript y generación 5/5 de páginas.
- El Compose efectivo mantiene **API y worker sin cambios**.
  Se verificó también que el Compose de reversión restaura
  la imagen anterior del frontend sin cambiar los otros servicios.

## Copia previa y construcción

Antes de editar los dos archivos existentes se creó y comprobó
el respaldo selectivo:

`/home/viewtv/viewtv-backups/descargas-sin-boton-actualizar-pre-20261120-191706.tar.gz`

SHA-256:
`d5ba8c2aecb911df52c8b1149cb54a558f544126035aa0d3b92450aa2bc67edf`

`tar -tzf` verificó exactamente:
- `frontend/components/downloads-panel.tsx`
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`

El test, los dos Compose y este documento son nuevos.

La imagen construida y versionada es
`viewtv-frontend:descargas-auto-0012`, ID de Docker:

`sha256:8bd8b697f903d9fde3c027460ff59c086d2f1e42659ce7c2ed0631115499f846`

Se mantuvo disponible la imagen anterior
`viewtv-frontend:catalog-auto-0012`.

## Despliegue aplicado y verificado

Con los cuatro Compose del proyecto más
`deploy/compose.catalog-auto-0012.yaml` y
`deploy/compose.descargas-auto-0012.yaml`,
se ejecutó únicamente:

`docker compose ... up --no-deps --no-build --force-recreate -d frontend`

**Solo se recreó `viewtv-frontend-1`**.

Resultados posteriores:
- `viewtv-frontend-1` usa la imagen nueva y está **healthy**.
- API `viewtv:predeploy-0012-release` sigue **healthy**.
- Worker `viewtv:catalog-auto-0012` continúa activo.
- Jellyfin y FlareSolverr siguen **healthy**.
- `VIEWTV_ENABLE_DOWNLOAD_START=false` confirmado después.
- Script `viewtv_release_smoke_0012_readonly.py`:
  **10/10 comprobaciones correctas**, incluyendo página HTML,
  API y proxy, perfiles, rutas 401 y salud Jellyfin.
- No se habilitaron nuevas descargas ni se movieron medios.
- No fue necesario modificar esquema ni crear otra copia de
  SQLite: el despliegue sustituye **exclusivamente el frontend**,
  que solicita GETs autenticados existentes.

## Cómo revertir, si fuera necesario

Sobre los mismos Compose anteriores, añadir **en este orden**
`deploy/compose.descargas-auto-0012.yaml` y, **el último**,
`deploy/compose.descargas-auto-0012-rollback.yaml`.

Aplicar solo:

`docker compose ... up --no-deps --no-build --force-recreate -d frontend`

Esto devuelve `viewtv-frontend:catalog-auto-0012` conservando
worker, API, Jellyfin, datos y configuración. Verificar
`docker ps` y repetir 10/10 smoke; no utilizar
`docker compose down -v` ni restaurar SQLite.

**La configuración de rollback se verificó, pero no se ejecutó**
porque el despliegue actual pasó todas las comprobaciones.

## Próximo bloqueo para terminar VIEWTV

Queda validar desde un perfil legítimo la **búsqueda nueva**,
selección, seguimiento, prueba de descarga autorizada y
organización hasta Jellyfin. Eso tiene prioridad sobre mejoras
cosméticas adicionales. El botón eliminado no implica haber
probado una descarga real ni su progreso completo.

La rama se actualiza con commit en español y el PR #2 permanece
abierto, en borrador y sin fusionar hasta autorización.
