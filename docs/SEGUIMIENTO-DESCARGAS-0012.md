# VIEWTV — Seguimiento seguro de descargas (trabajo local posterior a 0012)

Fecha: 19 de noviembre de 2026.

## Contexto de despliegue

- Último commit previo: `022d64e` (`0012_inicio_torrent`).
- Producción sigue en **`viewtv:predeploy-0011` / SQLite 0011**; la imagen `viewtv:predeploy-0012` está construida pero NO desplegada.
- Verificación automática activada en producción, **inicio automático desactivado**.
- No se ha reiniciado Docker, migrado SQLite de producción ni intervenido sobre torrents existentes.

## Implementación añadida

`GET /solicitudes/descargas?limit=25&offset=0`

- Requiere perfil autenticado con la dependencia existente `get_current_profile`.
- Consulta `Descarga` enlazada a `Solicitud` y exige `Solicitud.perfil_id == perfil.id`: no permite consultar trabajos de otros perfiles.
- Ordena por creación descendente e ID descendente para paginar de forma determinista.
- Límites: `limit` entre 1 y 100; `offset` no negativo; FastAPI devuelve 422 si no son válidos.
- Respuesta: `{elementos, total, limit, offset}`; cada elemento contiene `id`, `solicitud_id`, `titulo`, `estado`, `progreso` (0–1), `tamano_bytes`, `inicio_estado`, `estado_verificacion`, `creado_en` y `actualizado_en`.
- No devuelve hashes, URLs de descarga, rutas internas, mensajes de error libres ni identificadores de leases.
- Incluye el estado `requiere_revision` para que la interfaz pueda mostrar que se necesita intervención manual.
- Solo lectura: no envía órdenes de inicio, no modifica solicitudes ni manipula ficheros.

## Pruebas

`backend/tests/test_descargas_api.py`: 9 casos nuevos que cubren autenticación, aislamiento entre perfiles, campos públicos, `requiere_revision`, paginación y parámetros inválidos.

Validación local: **310 passed**, **2 avisos de deprecación** y Ruff sin errores sobre los archivos nuevos/cambiados. No se ha modificado el esquema 0012.

## Pendiente (prioridad)

1. El usuario se encarga de revisión visual. Integrar una vista de seguimiento en `frontend/components/viewtv-app.tsx`, con contrato en `frontend/lib/api.ts`; mostrar progreso, verificación y avisos de `requiere_revision` sin datos internos.
2. Corregir transición transitoria `stoppedDL` después de POST de inicio sin ocultar pausas manuales.
3. Diseñar revisión manual segura y autorizada, sin reintentos automáticos indefinidos.
4. Repetir pruebas, respaldo nuevo de producción y ensayo 0011→0012 antes del despliegue.
5. Prueba con contenido autorizado; después organizador de `Peliculas`/`Series`, escaneo Jellyfin y reproducción PWA.
6. Revisar los commits locales anteriores y los secretos antes de publicar la rama completa.

## Seguridad operativa

No ejecutar `docker compose down -v`, `git clean`, `git add .`, reiniciar torrents ajenos ni activar la bandera de inicio sin aprobación. Los respaldos se conservan en `~/viewtv-backups`.
