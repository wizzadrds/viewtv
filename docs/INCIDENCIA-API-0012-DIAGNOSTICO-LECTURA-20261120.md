# VIEWTV — API 0012 reiniciándose: diagnóstico sin intervención

Fecha: 20-11-2026. Rama de documentación:
`viewtv-seguimiento-descargas-0012`.

**LECTURA EXCLUSIVA. Sin cambios en Docker, SQLite, Compose ni medios.**

## Síntoma confirmado

La consulta `docker ps` en Ubuntu/WSL mostró:
- `viewtv-api-1`: imagen `viewtv:local`, estado
  `Restarting (255)`.
- `viewtv-worker-1`: `viewtv:predeploy-0012-release`, activo.
- Frontend, Jellyfin y FlareSolverr continuaban iniciados.

El filtro de `docker logs --tail 120 viewtv-api-1` volvió a mostrar:
`ERROR [alembic.util.messaging] Can't locate revision identified
by '0012_inicio_torrent'`.

`docker image inspect` confirmó **dos imágenes diferentes**:

| Referencia de imagen | SHA256 de la imagen | Creación UTC |
|---|---|---|
| `viewtv:local` (también `viewtv:rollback-worker-0008`) | `7dc447a61bb20f1d5de3d316c3b3b50aa5a4966df63779e6587a50388f7c210c` | 2026-11-18 20:55 |
| `viewtv:predeploy-0012-release` | `cc73b747a98344dfd429a5aa8064caf6d518083dec2e9e100255022b4774e17f` | 2026-11-19 19:19 |

En la **rama de desarrollo**, `git grep` identificó
`backend/migrations/versions/0012_inicio_torrent.py`
con `revision = "0012_inicio_torrent"`, y
`backend/migrations/versions/0013_cola_organizacion.py`
con `down_revision = "0012_inicio_torrent"`.

Estos datos sustentan una **sospecha fuerte** de incompatibilidad entre
el historial de migraciones disponible en la imagen API y el esquema
que espera la SQLite desplegada. **No se ha inspeccionado el
contenido de las migraciones empaquetadas en las imágenes**, por lo
que no se presenta como causa raíz demostrada al 100 %.

## Secuencia segura de recuperación propuesta, NO ejecutada

1. Registrar y validar primero el alcance del incidente, puertos
   necesarios, dependencias y estado de copias de seguridad.
2. **Antes de cualquier escritura**, identificar la ruta de la SQLite
   real sin revelar secretos, parar escrituras controladamente
   cuando se apruebe y tomar un respaldo consistente, verificado
   con SHA-256 y recuperación de lectura de una copia.
3. Inspeccionar las revisiones Alembic dentro de las dos imágenes
   de modo no destructivo, verificar qué migración espera el DB y
   cotejar versión API/worker/SQLite. No fabricar versiones faltantes,
   ni usar `stamp`, `downgrade` o `upgrade` a ciegas.
4. Preparar un cambio **coordinado** de API y worker hacia imágenes
   con la misma cadena de migraciones y un esquema compatible,
   con etiquetas verificables y recuperación aprobada.
5. Ensayar primero en una **copia** de la SQLite, con posibilidad de
   revertir; documentar tests de arranque, migración y rollback.
6. Solo con autorización y respaldo nuevo, aplicar el plan
   controlado a producción; validar servicio, salud y reversión.

## Controles respetados

No se ha leído ni impreso `.env`, contraseñas, PIN ni claves;
no se han lanzado migraciones, reinicios, reconstrucciones de imagen,
descargas, movimientos NTFS ni limpiezas de contenedores.
El PR #2 continúa en borrador. VIEWTV 0013 sigue desactivado.

Este documento es **nuevo**: no existía una versión previa
que respaldar. El análisis se basó en consultas de solo lectura.
