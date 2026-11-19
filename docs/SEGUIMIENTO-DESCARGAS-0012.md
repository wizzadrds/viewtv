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


## Revisión de `stoppedDL` transitorio

Se ha corregido la monitorización cuando qBittorrent acepta una orden de inicio pero todavía responde `stoppedDL` sin progreso.

- El monitor concede **90 segundos** de tolerancia solo a descargas con `inicio_estado=iniciada`, `estado=enviada`, progreso cero y `stoppedDL`; utiliza `actualizado_en` del registro de confirmación de inicio.
- Si durante ese intervalo aparece actividad, se registra `descargando`; las pausas posteriores se muestran inmediatamente.
- Si sigue detenido tras ese intervalo, vuelve a aplicarse la interpretación `pausada`; no queda oculto indefinidamente.
- Los estados de torrents antiguos o con `inicio_estado=no_requerido` siguen interpretándose como antes.
- Las pruebas nuevas cubren parada transitoria, parada persistente después del margen y pausa manual tras actividad.
- No se requiere una migración de base de datos adicional ni se activan torrents desde el monitor.

La corrección quedó registrada en el commit `b1e1d8d`, con 313 pruebas aprobadas y Ruff sin errores.


## PWA: pestaña «Descargas» (siguiente hito)

Se ha integrado en el frontend una pestaña separada de «Biblioteca» y «Descargas», con accesibilidad para mando de TV y diseño responsive.

- Tipos de respuesta documentados en `frontend/lib/api.ts` (`DownloadItem` y `DownloadsResponse`).
- Componente `frontend/components/downloads-panel.tsx`: consume exclusivamente `GET /solicitudes/descargas`, muestra estados de inicio y verificación, porcentajes, tamaño de descarga y el aviso `requiere_revision`.
- No se muestran hashes, rutas internas, URLs de descarga ni mensajes internos de error. **No hay botón para iniciar/reanudar torrents**.
- Paginación de 20 registros con botones accesibles. El refresco automático se realiza cada 15 segundos cuando la pestaña está visible, con cancelación de peticiones al salir/cambiar de perfil y protección contra respuestas fuera de orden.
- Se vuelve a la pantalla de inicio de sesión ante un HTTP 401, sin reutilizar datos de otro perfil.
- CSS de `frontend/app/globals.css` mantiene el estilo existente de VIEWTV y muestra la navegación también en pantallas estrechas.

### Validación

- `tsc --noEmit`: correcto con TypeScript del proyecto.
- ESLint: correcto en los archivos nuevos y modificados de la PWA.
- Pruebas completas de backend: **313 correctas**, 2 avisos de deprecación.
- `git diff --check`: correcto.
- Build completo de **Next.js 15.5.28** ejecutado con `node:22-bookworm-slim` en Docker efímero, sin red, mediante `npm run build`: **compilación de producción correcta**. Se han corregido cinco advertencias de compatibilidad CSS mediante `flex-start` / `flex-end`, conservando el diseño.
- **Pendiente:** comprobación visual real en navegador y televisión. La compilación no implica despliegue ni inicio de servidores.

### Pendiente de validación por el usuario

Comprobar visualmente la nueva pestaña en navegador/TV: legibilidad, estados vacíos y de revisión, progreso, botones de paginación, foco y navegación con mando, tamaños de pantalla. La UI no se ha desplegado todavía en producción.

No se ha migrado SQLite real ni se ha activado el inicio automático de torrents.
