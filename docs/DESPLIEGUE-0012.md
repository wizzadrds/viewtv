# VIEWTV — Despliegue controlado de 0012 y PWA real

**Fecha:** 19 de noviembre de 2026. **Estado:** desplegado y comprobado en la instalación Windows/WSL local.

## Resultado

- API y worker: imagen `viewtv:predeploy-0012-release` (ID `sha256:cc73b747a98344dfd429a5aa8064caf6d518083dec2e9e100255022b4774e17f`).
- SQLite real: revisión Alembic `0012_inicio_torrent` en el volumen `viewtv_viewtv_data`, integridad `ok`, sin errores de claves foráneas.
- Registros conservados: **2 perfiles, 1 solicitud, 0 descargas** en el momento del despliegue. No se ha leído, solicitado ni modificado ningún PIN.
- Worker: `VIEWTV_ENABLE_DOWNLOAD_VERIFICATION=true` y `VIEWTV_ENABLE_DOWNLOAD_START=false` comprobados en el entorno real del contenedor.
- PWA real: imagen `viewtv-frontend:predeploy-0012` (ID `sha256:40aa49e983f0e738f4cd9d3a1f161f355388cc5611308b9c294ba410e24d9cd4`).
- Acceso local a la página real: **http://127.0.0.1:3000**. Login con el perfil y PIN actuales del usuario. Es independiente de la DEMO de `3001`.
- API real: `http://127.0.0.1:8000/health` devuelve `estado=ok`; endpoint de descargas devuelve 401 sin cookie y el proxy de la PWA conserva esa autenticación.
- API, frontend, FlareSolverr y Jellyfin comprobados saludables. El worker en ejecución.
- No se ha iniciado ni modificado ningún torrent durante el despliegue. No se han borrado volúmenes ni medios.

## Validación previa antes de tocar producción

1. Suite de desarrollo backend: **347 pruebas aprobadas**, con dos avisos de deprecación.
2. TypeScript y ESLint de la PWA sin errores; build Next.js 15.5.28 correcto.
3. Nueva imagen frontend multi-stage con `frontend/Dockerfile` + `frontend/.dockerignore` y Next.js `output: standalone`; se ejecuta sin dependencias de desarrollo y como usuario no root.
4. Prueba de imagen frontend compilada contra API DEMO en red temporal: HTML 200, proxy de perfiles correcto, descargas sin cookie 401. Red y contenedor de prueba eliminados al terminar.
5. Backup transaccional de SQLite real `0011`; migración `0011→0012` sobre copia, integridad/foreign keys y cuentas correctas.
6. Ensayo aislado de reversión `0012→0011` sin pérdida de registros; NO se ha revertido la base real.
7. Contrato de Docker Compose: imagen 0012 en API y worker, verificador activo, inicio automático desactivado, `/media` solo lectura en worker, web accesible solo en loopback.

## Respaldos de SQLite y configuración

**Antes de migrar (0011)**: `~/viewtv-backups/viewtv-predeploy-0012-20261119-191737Z/`

- `viewtv-0011.sqlite3` SHA-256 `360ce78d8ccca4a7a26ef4b65dd9f0b346d9b1b7b61143afd65728e7ab8a38a0`.
- Configuraciones de Docker y `.env` guardados en carpeta privada con permisos restringidos; la copia `.env` NO se sube a GitHub.
- `ensayo-0012.sqlite3` y `ensayo-revertido-0011.sqlite3` son COPIAS de ensayo, no bases de producción.

**Después de migrar (0012)**: `~/viewtv-backups/viewtv-postdeploy-0012-20261119-193039Z/`

- `viewtv-0012.sqlite3` SHA-256 `0aff9ffa0c0afb3f11b6a9dc2d7123acccdec96f167de2701cd9d0e5c80cfd3d`.
- `manifest.json` documenta versión, conteos, integridad, imágenes y banderas.

Los respaldos están fuera del repositorio, no son públicos y no están enlazados al PR. No borrar ni sobrescribir.

## Reproducibilidad de los servicios

Superposición comprobada (siempre desde la raíz `~/projects/viewtv`):

```bash
docker compose -f compose.yaml -f compose.production.yaml \
  -f ~/viewtv-backups/compose-verification-enabled.yaml \
  -f compose.release-0012.yaml ps
```

`compose.release-0012.yaml` fija las imágenes de la versión, fuerza inicio automático falso y verificación verdadera y añade la web con puerto `127.0.0.1:3000`. No usar `docker compose down -v`.

## Recuperación ante incidencias (procedimiento, NO ejecutado en producción)

1. Registrar el estado actual y detener worker, API y frontend **antes** de modificar SQLite. No arrancar imágenes antiguas contra esquema 0012.
2. Guardar siempre una última copia coherente del estado 0012 (por si hay solicitudes nuevas) antes de intentar recuperar.
3. Decidir si es posible revertir `0012→0011` con Alembic sin operaciones de inicio registradas, o restaurar el backup de 0011. El ensayo de downgrade se hizo únicamente sobre copia; no ejecutar directamente en vivo sin revisión.
4. Para restauración, hacerlo con API/worker detenidos, con una herramienta aislada y el volumen SQLite apropiado; verificar checksum del backup, `PRAGMA integrity_check`, FK y revisión `0011` ANTES de arrancar 0011. La restauración podría perder datos posteriores al backup y necesita aprobación expresa.
5. Arrancar API y worker con `compose.yaml`, `compose.production.yaml` y `compose-verification-enabled.yaml`, sin el override 0012, y revisar salud. Mantener inicio automático desactivado.
6. Nunca usar las imágenes de rollback 0008 contra SQLite 0011/0012; ni limpiar el volumen `viewtv_viewtv_data`.

## Pendientes tras el despliegue

- Revisión visual por el usuario del perfil real **Adultos** en `http://127.0.0.1:3000` introduciendo su PIN habitual (nunca compartirlo). Confirmar que Biblioteca/Descargas y cierre de sesión funcionan.
- Es normal que Descargas esté vacío con 0 registros de descarga existentes: no confundir con un error de la interfaz.
- **Inicio automático todavía desactivado**. Antes de permitir operaciones reales de qBittorrent, completar política de revisión manual, pruebas con contenido autorizado y comprobar qBittorrent sin tocar el torrent ajeno.
- Organizador: solamente existe el planificador de solo lectura (`docs/ORGANIZADOR-SEGURO-PLAN.md`). Falta ejecución con leases, revalidación, idempotencia y escrituras confinadas en bibliotecas.
- Acceso externo/televisión no configurado: el puerto web escucha solo en `127.0.0.1` del ordenador. Definir seguridad de red antes de abrirlo a la LAN.
- Reconciliar PR #2, todavía en borrador, con los dos commits de documentación divergentes de la rama remota. No fusionar automáticamente ni forzar Git.

## Relación con los documentos anteriores

- `docs/SEGUIMIENTO-DESCARGAS-0012.md` recoge la implementación y su estado **antes** del despliegue, hoy actualizado por este documento.
- `docs/PREVISUALIZACION-0012.md` sigue describiendo correctamente la demo aislada del puerto `3001`.
- `docs/ESTADO.md` es un inventario histórico del 18/11/2026; esta página es la referencia para producción 0012 a 19/11/2026.
