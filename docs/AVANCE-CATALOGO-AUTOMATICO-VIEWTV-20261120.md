# VIEWTV — catálogo Jellyfin automático, probado y desplegado

**Fecha:** 20 de noviembre de 2026.
**Rama:** `viewtv-seguimiento-descargas-0012`.
**Prioridad del usuario:** terminar una aplicación funcional, documentar
cada avance en GitHub y posponer mejoras secundarias.

## Necesidad funcional

El usuario confirmó que **accede a VIEWTV y reproduce vídeos bien**
en el navegador. Preguntó por qué debe pulsar «Sincronizar» si Jellyfin
puede actualizarse periódicamente. El comportamiento anterior requería
un POST autenticado manual `/jellyfin/catalog/sync`, y después la UI
consultaba la SQLite. Al cerrar el navegador no había ningún proceso
periódico encargado del catálogo.

## Comportamiento implantado

1. `backend/app/jellyfin.py`: se ha extraído
   `synchronize_catalog(session, client=None)`, reutilizable por API
   y worker. Conservar el endpoint POST autenticado para mantenimiento;
   **no mostrar botones manuales al usuario**. Una sincronización aplica
   cambios de metadatos en una sola transacción SQLite y realiza rollback
   si Jellyfin falla a mitad de consulta.
2. `worker/catalog_sync.py` (nuevo): temporizador monotónico:
   **primer intento a los 60 segundos del inicio del worker**,
   después **cada 30 minutos** tras un éxito y **reintento a los
   5 minutos** si falla. Actualiza metadatos y disponibilidad en
   SQLite, **no mueve ni elimina vídeos ni inicia torrents**.
3. `worker/main.py`: ejecuta el temporizador sin bloquear el resto
   del ciclo cuando aún no vence; captura errores de Jellyfin para
   mantener vivo el worker y el procesador de descargas.
4. `frontend/components/viewtv-app.tsx`: elimina «Sincronizar» y
   «Actualizar biblioteca» de la vista vacía. Refresca la consulta
   GET del catálogo **cada 5 minutos solo con sesión y pestaña
   visibles**, al volver a la pestaña, y al regresar a «Biblioteca».
   Evita refrescar durante la pantalla de detalles y reproducción.
5. `backend/tests/test_worker_catalog_sync.py` (nuevo): pruebas
   de periodicidad, reintentos, parámetros de intervalo, reconciliación
   de metadatos ficticios y rollback cuando falla la segunda página.

La sincronización en el worker no depende de que una persona mantenga
la página abierta. El navegador solo actualiza lo que muestra.

## Pruebas antes del despliegue

- Backend completo: **626 passed, 2 warnings** de Starlette
  ya conocidos, exit 0 (45,08 segundos).
- Grupo focal (sincronizador, API y worker):
  **13 passed**, exit 0.
- Ruff `check`: correcto.
- Frontend TypeScript `tsc --noEmit`: correcto.
- Frontend ESLint: correcto en `viewtv-app.tsx` mediante dependencias
  de la instalación local, aisladas en contenedor sin red.
- Next.js 15.5.28 `npm run build`: **compilación de producción
  satisfactoria**, incluidas validación de tipos, lint y generación
  de páginas (5/5). La primera compilación sin red falló en
  `npm ci`; se repitió con red Docker normal y versiones fijadas
  por `package-lock.json`. No modificó contenedores de producción.
- Smoke de interfaz/API/Jellyfin: **10/10 correcto** antes y después
  del despliegue.

## Respaldo ANTES de los cambios

Para los cuatro archivos existentes se creó y verificó:

`/home/viewtv/viewtv-backups/sync-automatica-catalogo-pre-20261120-184827.tar.gz`

SHA-256:
`837eb894c843b0b516a1be71e8c14955c8effe016a2b6cfdc0b9cdb94a652cf2`

`tar -tzf` devolvió exactamente:
- `backend/app/jellyfin.py`
- `worker/main.py`
- `frontend/components/viewtv-app.tsx`
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`

Los nuevos ficheros, las pruebas y los Compose de despliegue no
tenían versión anterior.

Antes de cambiar **cualquier contenedor**, se creó una
**segunda copia consistente de la SQLite REAL**, desde el volumen
de Docker montado solo lectura, en contenedor sin red,
usuario sin privilegios, mediante `sqlite3.backup()`:

`/home/viewtv/viewtv-backups/catalogo-auto-pre-20261120-190627/viewtv-api-0012-before-recreate.db`

Tamaño: **163840 bytes**. SHA-256:
`b2c60c7795a4cffa98a3146747657c62005c924400b7cc1271ef3888be866c7b`

Verificación: `PRAGMA integrity_check=ok`, Alembic
`0012_inicio_torrent`, `foreign_key_check` con cero errores;
hash confirmado dos veces.

## Imágenes y despliegue verificado

Se construyeron dos imágenes VERSIONADAS sin sobreescribir las
anteriores:

- Worker: `viewtv:catalog-auto-0012`
  SHA Docker `e1b3dc759663ea1ec0153584207e1c60c19e824335df7d17753bd06ddcee239a`.
  Deriva de `viewtv:predeploy-0012-release` y solo incorpora el
  sincronizador, `worker/main.py` y `app/jellyfin.py`.
- Frontend: `viewtv-frontend:catalog-auto-0012`
  SHA Docker `9c1e3bed43a7f06f5c044db1dfd91905ebc899c927db545b4a3058143fce9959`.
  Compilación de Next.js desde la rama autorizada.

El override versionado
`deploy/compose.catalog-auto-0012.yaml` fue validado y aplicado
como último Compose mediante:

`docker compose ... -f deploy/compose.catalog-auto-0012.yaml up
--no-deps --no-build --force-recreate -d worker frontend`.

Los cuatro Compose anteriores se mantuvieron; el cambio solo
recreó **frontend y worker**. API, Jellyfin, FlareSolverr,
volúmenes, .env y torrents no se modificaron. No se habilitó
`VIEWTV_ENABLE_DOWNLOAD_START`: sigue `false`.

### Evidencia después del despliegue

- `viewtv-frontend-1` → `viewtv-frontend:catalog-auto-0012`,
  **healthy**.
- `viewtv-worker-1` → `viewtv:catalog-auto-0012`, activo.
- API → `viewtv:predeploy-0012-release`, **healthy**;
  Jellyfin y FlareSolverr, **healthy**.
- Primer ciclo automático del worker tras iniciar:
  **HTTP 200** al GET de Jellyfin `/Items`;
  log **«Catálogo Jellyfin actualizado: 1 medios»**.
  No hubo intervención manual ni POST del navegador.
- Smoke integrado posterior: **10/10 correcto**.
- Inventario posterior de SQLite en lectura exclusiva:
  2 perfiles, 2 medios, 1 disponible en Jellyfin,
  1 solicitud fallida preexistente y **0 descargas**,
  iguales a los conteos antes del cambio.
- No se ha alterado la biblioteca de archivos multimedia.

### Reversión sin restaurar la base

Las imágenes originales se conservan:
`viewtv:predeploy-0012-release` y
`viewtv-frontend:predeploy-0012`.

Si hay que deshacer el cambio funcional, usar los mismos cuatro
Compose originales más, **en este orden**, los dos archivos
versionados:

1. `deploy/compose.catalog-auto-0012.yaml`
2. `deploy/compose.catalog-auto-0012-rollback.yaml` (último).

Aplicar `up --no-deps --no-build --force-recreate -d worker frontend`,
verificar salud del frontend, API y worker y repetir los 10 smoke.
Este rollback solo cambia imágenes; no requiere retroceder Alembic
ni restaurar SQLite, porque **no se alteró el esquema**.
No usar `docker compose down -v`, no volver a la imagen API
antigua `viewtv:local` ni restaurar datos a ciegas.

## Límites conscientes y siguiente hito

- La frecuencia se mantiene en memoria del único worker actual;
  tras reiniciarlo espera 60 s para la primera actualización.
  Con varios workers futuros haría falta una planificación
  exclusiva o leader lock para evitar trabajo repetido.
- No hay garantía de catálogo actualizado al segundo; con el
  intervalo elegido puede tardar hasta aproximadamente 35 minutos
  en reflejarse en una pestaña visible. No confundir la
  actualización periódica de metadatos con la exploración
  instantánea de Jellyfin.
- La API de sincronización manual continúa disponible para
  mantenimiento autenticado, aunque se retiró el botón público.
- El usuario confirmó reproducción correcta; **no se han probado
  aún la búsqueda nueva, selección, descarga, seguimiento de un
  trabajo y organización automática**. Eso tiene prioridad sobre
  nuevas mejoras cosméticas.
- No se ha hecho merge del PR #2. Subir cada avance con pruebas
  y documentación al branch autorizado, en español.

**Decisión:** catálogo automático operativo y monitorizado,
sin alterar descargas ni medios. La aplicación es más utilizable;
el siguiente bloqueo real son las solicitudes/búsqueda.
