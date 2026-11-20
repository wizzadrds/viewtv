# VIEWTV — inicio restringido a una única descarga

**Fecha:** 20-11-2026.
**Rama:** `viewtv-seguimiento-descargas-0012`.
**Plan maestro:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Problema del producto resuelto

Después de implementar la selección, el envío detenido y el control
de alta por ID, existía un peligro concreto antes de la primera
transferencia real: `worker/main.py` invocaba `process_one_start`
sin ID, y `claim_next_start` reclamaba **el primer inicio pendiente
de toda la cola**. Por tanto, habilitar el inicio para un torrent de
prueba podía iniciar otro diferente.

La solución permite autorizar un futuro ensayo **solo para la misma
ID que se emplea al enviar el torrent**. No se han activado
transferencias ni manipulado torrents productivos.

## Cambios implementados

1. `backend/app/download_start_queue.py`:
   `claim_next_start(..., allowed_download_id=...)` acepta una ID
   individual opcional. La valida como entero positivo SQLite,
   rechazando cero, booleanos, cadenas, negativos y valores fuera de
   rango. Aplica la condición por ID en **ambas partes** de la
   transacción SQLite: selección y actualización del lease.
   No consume intentos ni reclama otra descarga si no existe la
   ID solicitada. Mantiene compatibilidad con pruebas anteriores
   cuando la ID no se pasa.
2. `worker/download_starter.py`:
   `process_one_start(..., allowed_download_id=...,
   expected_save_path=...)` valida el destino **antes del lease**.
   En modo ensayo exige la etiqueta exacta
   `viewtv-descarga-<ID>`, una única coincidencia del hash persistido
   en SQLite y una ruta staging Windows sin componentes `..`.
   Sigue enviando exclusivamente
   `POST /api/v2/torrents/start` con el **hash identificado**.
   Conserva la prevención de doble orden: un inicio ya activo
   se reconcilia sin POST, una respuesta ambigua se pospone y
   una pausa manual no se reanuda silenciosamente.
3. `worker/main.py`:
   `VIEWTV_ENABLE_DOWNLOAD_START=true` **no es suficiente**;
   también debe existir una ID válida en
   `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID`.
   Esa ID se utiliza tanto para el envío como para el inicio,
   que conservan sus **dos autorizaciones independientes**.
   Con ID ausente, se informa de la situación, se sigue atendiendo
   a búsquedas, supervisor y Jellyfin, y **no se llama al iniciador**.
4. `backend/tests/test_worker_main_start.py`: ajusta las pruebas
   del ciclo para comprobar que se pasa el ID y el staging.
5. Nuevo `backend/tests/test_release_one_torrent_start.py`:
   casos integrados sobre dos descargas ficticias y qBittorrent simulado.
6. Nuevo Dockerfile
   `deploy/Dockerfile.inicio-torrent-unico-0012` y override
   `deploy/compose.inicio-torrent-unico-0012.yaml`. El overlay
   cambia **solo el worker**, sin esquema, API ni frontend.

## Pruebas realizadas sin red ni torrents reales

Con SQLite en memoria, `FakeQbit` y
`QBittorrentClient(httpx.MockTransport)`, se verificó:

- Una ID autorizada para el **segundo** torrent solo inicia ese
  hash; el primero permanece pendiente, sin lease ni intentos.
- Una ID inexistente no puede reclamar otro inicio pendiente.
- Rutas de staging omitidas o ajenas y objetivos no válidos
  se rechazan antes del lease.
- Hash, etiqueta, ruta y estado inesperados, así como varias
  coincidencias, impiden enviar órdenes POST.
- Si la ID correcta ya está descargando, se registra como
  iniciada sin repetir ninguna orden.
- Consulta GET del cliente HTTP real con etiqueta de la ID y
  POST `/api/v2/torrents/start` con **solo** el hash autorizado,
  simulados sin conectarse a ningún servicio externo.
- El flag de inicio sin ID no llama a qBittorrent y mantiene
  el resto del ciclo del worker.
- Se conservan las regresiones de recuperación tras POST
  ambiguo y propiedad del lease.

**Batería focal:** 42 pruebas aprobadas.
**Suite backend completa:** **684 pruebas aprobadas**, 2 advertencias
de deprecación ya conocidas de Starlette, exit 0 (106,56 s).
**Ruff y `git diff --check`:** sin errores.
**Smoke API/frontend/Jellyfin:** **10/10** antes y después del
despliegue; seguridad HTTP 401 y health HTTP 200 preservados.

## Archivo previo y respaldo

Antes de editar los cinco archivos existentes, se creó:

`/home/viewtv/viewtv-backups/inicio-torrent-unico-pre-20261120-201435.tar.gz`

SHA-256:

`dd8115109b90ea6f256b31e995bb5dcc9c4600fa8b5e4cfb205b9daabd40d518`

`tar -tzf` verificó exactamente:
- `backend/app/download_start_queue.py`
- `worker/download_starter.py`
- `worker/main.py`
- `backend/tests/test_worker_main_start.py`
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`

Los tests integrados nuevos, Dockerfile, Compose y este informe no
tenían versión anterior.

## Despliegue y reversión

Imagen nueva: `viewtv:inicio-torrent-unico-0012`.

ID Docker:
`sha256:28e32188e34072fe096d8a12b60790f4f1fb273a03333f003a77ee44349a7f84`.

Se construyó sobre `viewtv:ensayo-torrent-unico-0012`,
copiando únicamente cola de inicio, iniciador y main.

### Respaldo consistente antes de recrear worker

`/home/viewtv/viewtv-backups/inicio-torrent-unico-despliegue-pre-20261120-202053/viewtv-api-0012-before-recreate.db`

SHA-256:
`7b9c5c05f079dc845aac12a0bd623ef7f72b7ff8b18d81c6f2008ba3d36069a7`

Copiado mediante la API online de SQLite desde un contenedor
efímero **sin red**, volumen origen **solo lectura**, usuario
sin privilegios. Tamaño **163840 bytes**,
`integrity_check=ok`, revisión `0012_inicio_torrent`,
cero errores de claves foráneas y hash confirmado
en el host. No se restauró SQLite.

### Despliegue efectivo

Tras validar `docker compose config` con los cuatro Compose base
y los overrides anteriores, se añadió como última capa
`deploy/compose.inicio-torrent-unico-0012.yaml`.
Se ejecutó **solo**:
`docker compose ... up --no-deps --no-build --force-recreate -d worker`.

No se cambió ni reinició API, frontend, Jellyfin ni FlareSolverr,
ni se modificaron medios o servicios Windows.

El Compose y las variables verificadas dentro del worker mantienen:
`VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
`VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=""`,
`VIEWTV_ENABLE_DOWNLOAD_START=false`.

Resultado posterior:
- Worker `viewtv:inicio-torrent-unico-0012` **activo**,
  sigue ejecutando ciclos de cola.
- API `viewtv:predeploy-0012-release`, frontend
  `viewtv-frontend:solicitudes-0012`, Jellyfin y
  FlareSolverr **healthy**.
- 10/10 comprobaciones de salud, proxy, perfiles y acceso protegido.
- Inventario SQLite read-only: **2 perfiles, 2 medios,
  una solicitud fallida previa y cero descargas nuevas**.
- No se realizó POST real de alta ni de inicio de torrents.

**Nunca activar el inicio a escala global**. Para una prueba real
se requiere comprobar en lectura el torrent elegido, el hash
real, la ubicación staging Windows, la autorización de la persona
y una reversión manual. Solo entonces autorizar progresivamente
un alta detenida y después el inicio de esa misma ID.

Si se produjera una incidencia con la imagen nueva, no
volver a `viewtv:ensayo-torrent-unico-0012` mientras alguien
pueda habilitar el inicio: aquella imagen carecía del filtro por
ID de esta fase. Como medida reversible conservadora,
`docker compose ... stop worker` con los Compose efectivos,
sin detener API, frontend ni Jellyfin y sin borrar datos.
Esta medida se **documenta, no se ejecuta** mientras el worker
continúe sano. Después reparar hacia delante y repetir las pruebas.

## Pendientes reales de VIEWTV

1. Usuario: comprobar una búsqueda y selección nuevas en
   «Buscar y pedir» con contenido autorizado; verificar aparición
   en Descargas.
2. Comprobar sin escribir la ubicación de qBittorrent en Windows
   y el directorio de staging usado por VIEWTV.
3. Aprobar y ejecutar una única prueba real de envío detenido,
   inicio, progreso y terminación; evitar cualquier torrent ajeno.
4. Integrar organizador seguro 0013: publicar solo ese medio en
   destino autorizado y comprobar detección en Jellyfin.
5. Verificar recuperación y reversión, y cerrar el PR solamente
   con autorización explícita.

**Limitación:** pruebas HTTP y SQLite ficticias no acreditan
la integridad de una transferencia real ni del organizador. No se
declara completo el proyecto por esta entrega.
