# VIEWTV 0012 — selección segura y prueba integral del recorrido principal

**Fecha:** 20-11-2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Objetivo del usuario:** sacar la aplicación cuanto antes y documentar
cada incremento. Alineado con
[PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Bloqueo funcional real descubierto

Ya funcionaban la API, el login y la reproducción (confirmados por el usuario),
el catálogo automático, la pantalla «Buscar y pedir» y el seguimiento visual.

El worker tenía una discrepancia importante entre **seleccionar**,
**registrar un torrent en qBittorrent** e **iniciar su transferencia**:

- `worker/main.py` invocaba `process_one_download()` **en cada
  ciclo**, incluso si `VIEWTV_ENABLE_DOWNLOAD_START=false`.
- `worker/download_processor.py` añadía el torrent mediante
  `QBittorrentClient.add_torrent(stopped=True)` tras una selección.
- Por tanto, desactivar el **inicio** impedía la orden de arranque,
  pero NO impedía que el torrent apareciese en el gestor como
  registro detenido. Eso podía sorprender al usuario al probar la UI.

## Corrección necesaria para poder probar sin registrar torrents

`worker/main.py` incorpora ahora una autorización diferenciada:

- `VIEWTV_ENABLE_TORRENT_SUBMIT=false` **por defecto**:
  no se llama a `process_one_download`, por lo que no se envían
  ni reconcilian altas de torrents seleccionados en qBittorrent.
- `VIEWTV_ENABLE_DOWNLOAD_START=false`: sigue bloqueada la
  orden explícita de inicio de transferencia.

La búsqueda mediante `process_one_request`, la supervisión de
descargas existentes y la sincronización de Jellyfin siguen en el
ciclo del worker. Una selección queda registrada en SQLite en estado
`seleccionada` y aparece en la pestaña Descargas, sin consumir intentos
de envío ni provocar alta en el cliente torrent.

**No confundir con funcionalidad completa de descarga:** el permiso
de alta y el permiso de inicio se habilitarán solo durante una prueba
real explícitamente autorizada, después de verificar destino,
torrent identificado y procedimiento de reversión.

## Prueba integrada de la aplicación, sin recursos productivos

Archivo nuevo: `backend/tests/test_release_search_selection_flow.py`.

Para evitar escribir en la base productiva o tocar proveedores se
utilizó **SQLite en memoria**, `FastAPI TestClient`, el worker real
`process_one_request`, un `JackettClient` real con transporte
`httpx.MockTransport` y **XML Torznab ficticio**. Sin red, qBittorrent,
nombres de usuarios reales, títulos reales, URLs de torrents reales
o movimientos NTFS.

Se verificó:

1. `POST /solicitudes` por título, tipo y año; petición guardada y
   duplicado activo rechazado con **409**.
2. Reclamación del lease por worker, búsqueda de tipo `movie` y
   `tvsearch`, consulta Torznab simulada y dos resultados convertidos
   y guardados.
3. `GET /solicitudes`: pasa a `esperando_seleccion`.
4. `GET /solicitudes/{id}/resultados`: orden por calidad y
   **sin exponer URLs, enlaces magnet, hash ni clave interna**.
5. `POST /solicitudes/{id}/seleccion`: devuelve 201; segundo intento
   es rechazado con 409.
6. `GET /solicitudes/descargas`: aparece exactamente una descarga
   `seleccionada`, progreso 0, sin datos internos del torrent.
   SQLite confirma que `qbittorrent_hash` sigue nulo,
   `intentos_envio=0` e `inicio_estado=no_requerido`.
7. Resultado vacío: `sin_resultados` y ninguna descarga.
8. Aislamiento: un segundo perfil no puede consultar ni seleccionar
   resultados ajenos, ni ver descargas ajenas.

Además, `backend/tests/test_worker_main.py` comprueba que
el worker siga buscando y supervisando sin invocar el envío de torrent
cuando el flag está desactivado. Las regresiones históricas en
`backend/tests/test_worker_main_verification.py` fijan explícitamente
el modo autorizado para conservar su cobertura y tienen una nueva
prueba del modo bloqueado.

## Validaciones finales

- Tests focales del nuevo gate y recorrido:
  **11 correctos**, una advertencia de dependencia conocida.
- Suite completa backend: **632 aprobados**, dos avisos de
  deprecación conocidos, exit code 0, 81,19 s.
- Ruff `check`: correcto.
- Nueva imagen worker creada sin red:
  `viewtv:seleccion-sin-envio-0012`, ID Docker:
  `sha256:bafa362bfa9128fda5461e3d01d2394328522edbb9d384668a3dbfe89d725c4b`.
  Inspección de la imagen confirmó el código con
  `SUBMISSION_ENABLED` y la condición de envío.
- `docker compose config` comprobó que las imágenes API/frontend
  no cambian y que `VIEWTV_ENABLE_TORRENT_SUBMIT=false` y
  `VIEWTV_ENABLE_DOWNLOAD_START=false`.
- Tras recrear **solo** `viewtv-worker-1`:
  worker activo con nueva imagen, API, frontend, Jellyfin y
  FlareSolverr saludables.
- `viewtv_release_smoke_0012_readonly.py`: **10/10 PASS**.
- Inventario de SQLite de **solo lectura** después:
  2 perfiles, 2 medios, 1 solicitud fallida anterior,
  0 nuevas descargas, mismo conteo previo.
- Logs worker: procesando ciclos, sin bloqueo por el nuevo gate.
- No se hicieron búsquedas ni selecciones de medios reales en nombre
  del usuario; no se habilitó ni inició ningún torrent.

## Respaldos previos, verificados

Antes de editar el worker y la primera batería de tests:

`/home/viewtv/viewtv-backups/seleccion-sin-envio-pre-20261120-194246.tar.gz`

SHA-256:
`587c6c2c54ee66f6bf53507fd3030d1e706fecfbeecfa4d9db67adf189152b45`

`tar -tzf` verificó:
- `worker/main.py`
- `backend/tests/test_worker_main.py`
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`

Para cambiar la batería adicional:
`/home/viewtv/viewtv-backups/pruebas-gate-envio-pre-20261120-195132.tar.gz`

SHA-256:
`e37350f88c19d1bf1e6393a8c72d87c0c59789968833bb1ba07e5b727da1e10c`

`tar -tzf`: solo
`backend/tests/test_worker_main_verification.py`.

Antes de recrear worker se creó una copia **consistente** de SQLite
desde volumen montado en **solo lectura** mediante
`sqlite3.backup()`, contenedor efímero sin red:

`/home/viewtv/viewtv-backups/seleccion-sin-envio-0012-pre-20261120-194801/viewtv-api-0012-before-recreate.db`

SHA-256:
`fead912adbcf5c58a04807b1f405ad218bc8cd6c17ededdec952da98cd179d40`

Comprobados 163840 bytes, revisión `0012_inicio_torrent`,
`integrity_check=ok` y cero errores de claves foráneas.
El hash se volvió a verificar. No hubo restauración.

Los tests integrados, override Compose y este informe son nuevos,
sin versión anterior que respaldar.

## Despliegue y reversión segura

Se mantuvieron los cuatro Compose originales de VIEWTV y los
overrides previos de catálogo, descargas y solicitudes. Se añadió
**en último lugar** el nuevo override:

`deploy/compose.seleccion-sin-envio-0012.yaml`

Se ejecutó:
`docker compose ... up --no-deps --no-build --force-recreate -d worker`

Solo se recreó el worker. API, frontend, Jellyfin y datos permanecieron
en sus versiones. La imagen anterior del worker se conserva como
artefacto de referencia.

**ADVERTENCIA de rollback:** la imagen anterior
`viewtv:catalog-auto-0012` **ignora el flag nuevo** y puede volver
a registrar torrents detenidos. NO constituye una reversión segura
mientras la selección esté habilitada en VIEWTV. No se proporciona
ningún Compose que invite a restaurar esa imagen inadvertidamente.

En caso de una incidencia de la nueva imagen, la medida fail-closed
**reversible** es detener solo el worker mediante el mismo proyecto
Compose (`docker compose ... stop worker`), sin alterar API, frontend,
SQLite ni Jellyfin. La búsqueda y sincronización automática se
pausarán temporalmente. Se debe diagnosticar y corregir hacia delante,
con las pruebas y el respaldo; no reinstalar la imagen vieja sin
aprobar y garantizar antes el bloqueo de alta de torrents. Esta
reversión de emergencia está **documentada, no ejecutada**.

Nunca usar `docker compose down -v`, forzar descargas ni restaurar
SQLite en caliente.

## Qué falta para completar VIEWTV

1. Usuario: introducir una solicitud legítima en **«Buscar y pedir»**,
   esperar resultados de Jackett real y seleccionar uno; observar
   estado `seleccionada` en Descargas, sin alta torrent.
2. Preparar **un único torrent de prueba autorizado**, origen/propiedad,
   ruta de staging, hash, modo detenido y reversión documentados.
3. Habilitar exclusivamente la autorización de **alta** para ese
   ensayo controlado; comprobar que solo el torrent seleccionado
   se incorpora correctamente.
4. Verificar destino y estados antes de habilitar la orden
   separada de **inicio** y seguimiento de la descarga.
5. Integrar el organizador mínimo 0013 y verificar que el contenido
   completado se publica sin duplicados y Jellyfin lo detecta.
6. Pruebas de recuperación, respaldo, reversión y cierre del PR
   solo tras autorización explícita.

No dar por terminado el proyecto por esta prueba sintética.
La primera versión reproduce bien medios existentes y ahora
puede preparar selecciones, pero **todavía no descarga ni
organiza automáticamente contenido nuevo**.
