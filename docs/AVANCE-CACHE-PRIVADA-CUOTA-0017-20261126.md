# VIEWTV 0017 — Caché privada con cuota, evicción y aislamiento

**Fecha de trabajo:** 26 de noviembre de 2026, Europe/Madrid.
**Repositorio:** `wizzadrds/viewtv`.
**Rama:** `viewtv-seguimiento-descargas-0012`, PR #2 se mantiene OPEN/DRAFT sin fusionar.
**Prioridad:** espacio y eliminación de películas vistas **antes** de la app Samsung; «VIEWTV Momentos» posteriormente.

## Alcance y resultado

Implementación de un **controlador real de tamaño y caducidad para nuevos temporales exclusivamente propios de ViewTV**, no una política sobre toda la caché del equipo.

Anteriormente la carpeta `/cache` apuntaba al bind `/mnt/c/VIEWTV/cache` de NTFS, cuyo modo visible en WSL era `0777`. No superaba las comprobaciones estrictas de propiedad (`0700`), por lo que el botón original de limpieza segura no podía operar ahí sin relajar garantías. **No se relajaron garantías para Windows ni se limpió esa carpeta.**

Se añade **un volumen Docker nombrado e independiente** `viewtv_cache_propia_0017` montado **solo en la API** en `/cache-gestionada`, separando claramente los temporales controlados de:

- `/cache`: bind antiguo en Windows; se deja intacto.
- `/media`: películas, series y originales con permiso de **solo lectura**; no se permite borrarlos desde la API.
- Caché de Jellyfin, configuración/transcodificaciones, TMDB SQLite y base SQLite ViewTV.
- Carpetas de qBittorrent y diarios privados del publicador Windows.

### Motor interno de caché (no endpoint de escritura)

`backend/app/cache_privada.py` introduce `guardar_temporal`, `estado_cache` y `limpiar_cache`. Para un nuevo escritor autorizado que utilice la biblioteca, el sistema:

1. Acepta una raíz propia y comprueba su UID, tipo de directorio y ausencia de escritura por terceros.
2. Inicializa una subcarpeta `viewtv-temporales` con permisos `0700` y marcador `.viewtv-cache-v1`, sin seguir symlinks.
3. Serializa inicialización con bloqueo de directorio y escrituras/limpiezas mediante `flock`; se corrigió un fallo real detectado en las pruebas de concurrencia, cuando existía el directorio antes que el marcador.
4. Escribe únicamente `viewtv-<identificador hexadecimal aleatorio de 32 caracteres>.tmp` y archivos `0600`, sin exponer al usuario una ruta o un endpoint de subida.
5. Limita cada temporal a **16 MiB** y el conjunto a la cuota configurada `cache_quota_gb=80` (80 GiB por defecto, parámetro validado entre 1 y 512 GiB). Antes de escribir, descarta temporales propios caducados a **14 días** y, si no basta, los más antiguos hasta poder respetar la cuota. No recorre subdirectorios ajenos.
6. Comprueba inodo, volumen, UID, permisos, tipo regular, contador de enlaces `=1` y marcador antes de borrar. Symlinks, hardlinks adicionales, nombres no permitidos, permisos inseguros, exceso de entradas o marcador corrupto **bloquean el conjunto de la operación**, no se eliminan por heurística.
7. Solo manipula el volumen de caché dedicado. Nunca llama al gestor de archivos Windows, Jellyfin o qBittorrent.

**Límite importante:** el motor **sí aplica una cuota a los archivos que se escriban a través de `guardar_temporal`**, pero **todavía no hay productores reales de temporales conectados** a este escritor. Por tanto, no se puede afirmar que se haya reducido la ocupación actual ni que el límite de 80 GiB se aplique al caché de otros programas. La caché propia comienza vacía.

### API y pantalla de espacio

- `GET /almacenamiento/resumen` (autenticado) incluye `cache_propia`: estado seguro, archivos, bytes, cuota y advertencia de que solo controla el escritor propio. El campo preexistente `cache_cuota_aplicada=false` se conserva para no afirmar que el límite es global.
- `POST /almacenamiento/cache/propia/limpiar` (autenticado) exige la frase exacta `LIMPIAR CACHE PROPIA`. Solo elimina temporales del volumen propio, y devuelve 409 sin filtrar rutas si falla cualquier verificación de confianza.
- `POST /almacenamiento/cache/limpiar` anterior permanece por compatibilidad, sin cambio de permisos ni ampliación de alcance.
- En la pestaña **Espacio** de la interfaz principal, la tarjeta muestra ahora «Caché privada de ViewTV» con cuota explícitamente parcial y un botón **Vaciar caché privada** que solo se habilita si hay temporales. Se muestra aparte la cantidad de caché heredada y de metadatos TMDB.
- No se cambia `/tv.html`, el reproductor, la gestión de torrents, el historial de películas vistas ni las solicitudes de retirada.

## Pruebas y seguridad

- Copia previa de código y documentación:
  `/home/viewtv/viewtv-backups/gestion-cache-propia-pre-20261126-195942.tar.gz`
  SHA-256 `40d6b82f5790b000dc462cea4c3cf2cd39096c3b57dd5473d96cdeda1b0da129`.
  Se verificaron hash y `tar -tzf`; no contiene `.env`, bases de datos, archivos multimedia ni torrents.
- Suite específica nueva `backend/tests/test_cache_privada_0017.py`: cuota efectiva por escritura, límite de tamaño, caducidad, marcadores, limpieza, raíz no confiable, symlink/hardlink, permisos, ficheros ajenos y concurrencia.
- Se añadieron pruebas a `backend/tests/test_almacenamiento_0015.py` para la API y su rechazo ante archivo extraño. **23/23 pruebas específicas PASS**.
- TypeScript `tsc --noEmit` PASS, ESLint del componente PASS.
- Pruebas de frontend **18/18 PASS**. Build Next.js de producción 0017 PASS.
- Imagen backend `viewtv:cache-propia-api-0017` sobre `viewtv:publicador-compatible-api-0016`: no modifica el control del publicador.
- Compose validado con un único volumen nuevo solo en la API, `/media:ro` en API y worker, worker sin cambios, catalogador igual, banderas de autoescritura/organización desactivadas, y el publicador Windows conservado.
- La migración SQLite permanece **0015** (sin nuevas tablas ni migraciones). Antes de desplegar se comprobaron **0 descargas activas**, **0 solicitudes procesándose**, integridad `ok` y FK correctas.
- **Suite completa backend: 1054/1054 PASS**, con 2 advertencias de deprecación de dependencias externas; suite ejecutada en contenedor sin acceso de red.
- Despliegue real realizado de forma limitada: sólo API `viewtv:cache-propia-api-0017` y frontend `viewtv-frontend:cache-propia-0017`. Ambos contenedores quedaron **healthy**. Worker, Jellyfin, catalogador y FlareSolverr conservaron imagen y proceso.
- Docker creó **una nueva unidad vacía** `viewtv_viewtv_cache_propia_0017` para la API, distinta al volumen de películas. La prueba en vivo de sólo lectura dio: `CACHE_VOLUMEN_INDEPENDIENTE=PASS`, `CACHE_PRIVADA_VACIA=SI`, `CACHE_CUOTA_PROPIA_GIB=80`; API 200 y acceso sin sesión a informe y limpieza 401.
- Versión Alembic `0015_gestion_espacio_vistas` sin cambios; `python -m worker.organization_windows_cli status` devolvió `listo`, conservando el modo general aprobado.
- Smoke posterior de sólo lectura **10/10 PASS**; análisis de reversión `check-rollback` **PASS**, sin ejecutar rollback ni borrar volumen.
- Resultado real: **ningún temporal en producción limpiado**, ningún vídeo ni torrent borrado, no se iniciaron descargas ni se alteró la SQLite de contenido. La cuota sólo controla futuros temporales que utilicen este escritor.

## Despliegue y rollback limitados

Archivos:

- `scripts/Dockerfile.cache-propia-api-0017`.
- `deploy/compose.cache-propia-0017.yaml` (solo API, frontend y volumen propio).
- `deploy/compose.cache-propia-rollback-0017.yaml`.
- `scripts/viewtv_cache_compose_verify_0017.py`.
- `scripts/viewtv_cache_deploy_0017.sh` (comprobación previa y operación de dos servicios).

Comprobación previa:

```bash
bash scripts/viewtv_cache_deploy_0017.sh check
```

Despliegue, **solo tras pasar pruebas y preflight**:

```bash
bash scripts/viewtv_cache_deploy_0017.sh deploy
```

Rollback de imágenes, con el volumen y sus datos intactos:

```bash
bash scripts/viewtv_cache_deploy_0017.sh check-rollback
bash scripts/viewtv_cache_deploy_0017.sh rollback
```

Ninguno de estos comandos usa `docker volume rm`, `down -v`, prune, borrados NTFS ni borrado de torrents.

## Pendiente de espacio antes de Samsung

La retirada física de películas **no está implementada**. El botón sigue siendo `Solicitar retirada`, y su petición puede cancelarse. La auditoría anterior 0016 encontró dos hardlinks propios vinculados a Jellyfin, pero **dos torrents estaban en uso** y una carpeta carecía de un diario válido. El sistema debe seguir negando una eliminación hasta tener autorización separada del administrador, comprobación atómica de estado e identidad, exclusión de streams, garantías NTFS/qBit y diario recuperable con medición real del espacio liberado.

Pendiente también conectar a `guardar_temporal` únicamente productores de caché propios que se diseñen; no convertir una cuota parcial en una garantía global. Terminar todo el sistema de retirada antes de desarrollar la app Samsung profesional y después «VIEWTV Momentos».
