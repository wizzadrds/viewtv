# VIEWTV — descarte seguro de selección incorrecta

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Relación:** [plan maestro](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Corrección del diagnóstico

El usuario ha confirmado que **él mismo eliminó** el torrent de
«Nadie 2» en qBittorrent, después de comprobar que el archivo no era
el correcto. Los eventos de qBittorrent fueron alta, reanudación,
detención y eliminación manual. No se atribuye la retirada al
worker ni a qBittorrent como error de estabilidad.

La base SQLite productiva conserva la descarga ID **1** y solicitud
**3** en `enviada`, `inicio_estado=pendiente`, progreso 0 %, con
hash histórico. Los GET actuales por etiqueta y hash devuelven cero.
No hay razón para recuperarlo o iniciarlo. El usuario desea que
VIEWTV descargue automáticamente **contenidos correctos**, no que
reactive un torrent descartado por contenido erróneo.

La coincidencia conservadora de palabras del título no garantiza la
identidad del archivo; no ampliar la cola global basándose en ese
filtro. El objetivo de automatización sigue abierto.

## Solución implementada sin migrar SQLite

- Endpoint autenticado
  `POST /solicitudes/descargas/{id}/descartar-incorrecta`.
  Rechaza peticiones de otros perfiles o cualquier descarga que
  no esté `enviada`, con inicio `pendiente`, 0 % y
  `inicio_intentos=0`, hash existente y **sin leases**.
  Antes de escribir, comprueba por GET **hash** y **etiqueta**
  que qBittorrent no contiene el torrent. Si no responde o existe
  cualquier coincidencia, devuelve **503/409** sin cambiar nada.
  Recomprueba estado/propietario/hash dentro de una transacción
  `BEGIN IMMEDIATE`.
- SQLite 0012 restringe el estado de descarga; para evitar una
  migración se conserva el registro con `estado=fallida` y la
  marca inequívoca `ultimo_error="Selección incorrecta descartada
  por el usuario."`, con `inicio_estado=requiere_revision`.
  La solicitud se marca `cancelada`, también conservada.
  Así ni la cola de alta ni la de inicio puede reclamarla.
- `GET /solicitudes/descargas` oculta por defecto solo estos
  descartes voluntarios (incluyendo correctamente totales y
  paginación). `?incluir_descartadas=true` ofrece historial
  de descargas completo; las fallidas por errores distintos se
  siguen mostrando.
- `frontend/components/downloads-panel.tsx` ofrece botón
  **«Descartar torrent incorrecto»** cuando hay un envío sin
  iniciar y con progreso cero; exige confirmación visible.
  No ejecuta una orden de borrado, detención ni arranque en
  qBittorrent, ni opera automáticamente al refrescar.
  Tras confirmarlo, el registro desaparece de «Mis descargas»
  y el usuario puede crear una búsqueda nueva.

**Importante:** el descarte en SQLite real **no se ha ejecutado**;
se deja al usuario confirmar el botón en su propia sesión.
La descarga ID 1 sigue bloqueada para nuevos envíos y arranque.

## Validación y producción

1. Tests del endpoint **41/41 PASS**: éxito y conservación de
   histórico, rechazo si hay torrent por hash o etiqueta,
   conexión qBittorrent caída, progreso/inicio/estado incompatibles,
   aislamiento de perfil y segunda llamada.
2. Backend completo **805/805 PASS**, 2 advertencias deprecadas
   no bloqueantes.
3. Build Next.js y validación TypeScript **PASS**.
4. `scripts/viewtv_descartar_copia_sqlite_sandbox.py` ejecutado
   con la copia SQLite real pasada a memoria, contenedor sin red,
   volumen solo lectura y qBittorrent simulado sin POST:
   **4/4 PASS** (descarte, pantalla limpia, historial, inicio
   bloqueado). La SQLite productiva no se tocó.
5. Solo API y frontend recreados separadamente con
   `--no-deps --no-build --force-recreate`, sin cambios de
   worker; imágenes `viewtv:descartar-incorrecta-api-0012`
   y `viewtv-frontend:descartar-incorrecta-0012`.
   La ruta de descarte sin login responde 401; smoke de
   producción de solo lectura **10/10 PASS**.
6. Worker existente `viewtv:qbit-async-0012`: envío
   `false`, inicio `false`, ID autorizada vacía. No se
   ha añadido ni eliminado ningún torrent mediante esta mejora;
   tampoco se tocaron `C:\VIEWTV\media\Peliculas`, Jellyfin
   o bibliotecas.

## Respaldos

- Código afectado antes de escribir:
  `~/viewtv-backups/descartar-seleccion-incorrecta-pre-20261121-000822.tar.gz`,
  SHA-256 `10584f14600933e5dc6b051663e5502690e96a7d24147b51c6e9fc945679f777`.
- Código de informe anterior y backlog, antes de corregir la causa:
  `~/viewtv-backups/aclaracion-eliminacion-usuario-pre-20261121-001336.tar.gz`,
  SHA-256 `c8626d96c48352a394dba34e0349b812a28f18e782e857cb05d5c79e5540a726`.
- SQLite coherente antes de desplegar:
  `~/viewtv-backups/api-resultados-predeploy-20261121-001217.db.tar.gz`,
  SHA-256 `b51fcead7f16e67d33c0f9413e24c32a981174e9a98e2c4cfebbc9cb763e535a`,
  `PRAGMA integrity_check=ok`, `foreign_key_check=0`.

Los tres `tar.gz` se verificaron mediante `tar -tzf`.

## Reversión y próximos pasos

`scripts/viewtv_compose_descartar_0012.sh` permite
`rollback-api` y `rollback-frontend`, restaurando las
imágenes anteriores de estos dos servicios sin recrear el worker,
migrar SQLite ni perder los datos. No usar
`docker compose down -v`, `git reset --hard` ni tocar
bibliotecas. PR #2 sigue draft, sin merge.

**Pendiente del usuario:** recargar la PWA, entrar en
«Mis descargas» y confirmar «Descartar torrent incorrecto» para
ID 1. Después hacer una búsqueda distinta y verificar que el
archivo ofrecido es el contenido esperado antes de seleccionarlo.
**Pendiente del desarrollo:** validar un torrent correcto y
autorizado, alta estable, inicio individual autorizado, transferencia,
verificación y publicación antes de habilitar la automatización
general que el usuario solicita.
