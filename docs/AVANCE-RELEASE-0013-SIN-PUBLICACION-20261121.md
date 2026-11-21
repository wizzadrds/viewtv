# VIEWTV — Release 0013 desplegada con publicación deshabilitada

**21/11/2026 · rama exclusiva `viewtv-seguimiento-descargas-0012`.**

## Resultado y límites

La barrera de arranque de servicios Windows 4551 ya está resuelta
**por cambio realizado por el usuario**: el registro local
`VerifiedAndReputablePolicyState` pasó a **0**. Con el archivo de
prueba aislado de `scripts/test_viewtv_windows_service_docker_0013.ps1`,
el SCM inició un servicio temporal bajo LocalSystem y el acceso a
Docker Desktop devolvió `WINDOWS_SERVICE_DOCKER_PROBE=DOCKER_ACCESS_OK`.
Se comprobó que no quedaban servicios ni carpetas de prueba.
Esto NO significa que el servicio de publicación de ViewTV esté instalado,
autorizado para uso general o aislado por un SID restringido.

Se ha desplegado la release 0013 únicamente en:
- `viewtv-api-1`: `viewtv:release-0013-api-candidate`, healthy.
- `viewtv-worker-1`: `viewtv:release-0013-worker-candidate`, en marcha.

Se conservaron `viewtv-frontend-1` (HLS ya comprobado por usuario),
`viewtv-jellyfin` y FlareSolverr **sin recrear**. Las imágenes API y
worker incorporan Alembic `0013_cola_organizacion`; la base real
ha migrado a esa versión.

**Publicación de Windows sigue deshabilitada** en ambos contenedores:
`VIEWTV_WINDOWS_PUBLICATION_MODE=disabled`.
`VIEWTV_ENABLE_ORGANIZATION=false` en worker;
`VIEWTV_ENABLE_DOWNLOAD_START=false`,
`VIEWTV_ENABLE_TORRENT_SUBMIT=false`.
`VIEWTV_ENABLE_AUTO_DOWNLOAD=true` y
`VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1`,
verificación de descargas activada, como antes.
No se creó, borró ni alteró ningún torrent, archivo multimedia
o dato histórico por decisión del publicador. No se instaló
el servicio persistente `ViewtvPublicador0013` ni se configuró
ningún permiso para un ID nuevo. No hay aún segunda película real
publicada automáticamente.

## Evidencia antes del despliegue

1. Desde rama limpia `71a6492`, se ejecutó un servicio SCM efímero
   con código ficticio en sandbox Windows; `PROBE_EXIT=0`,
   `DOCKER_ACCESS_OK`; protección de Windows desactivada por usuario.
2. Instantánea SQLite online de solo lectura:
   `/home/viewtv/viewtv-backups/api-resultados-predeploy-20261121-232158.db`.
   SHA-256:
   `66a92eea559d92d3dd0dae9b444e990593197e0405eef52edbf26b7b545bc604`.
   Revision `0012_inicio_torrent`, integridad OK, FK=0.
3. Ensayo sobre copia separada
   `/home/viewtv/viewtv-backups/ensayo-0013-20261121-232158.db`:
   Alembic `0012→0013→0012`, verificación después de
   cada transición. Recuentos invariantes:
   perfil=2, medio=3, solicitud=7, descarga=2, resultado_busqueda=64.
   No se probó rollback con trabajos 0013 activos.
4. Se recuperó el orden real de los archivos Compose de las labels
   actuales, sin escribir en la otra worktree ni imprimir `.env`.
   `scripts/viewtv_release_0013_compose_safe.sh` comprueba la
   whitelist de rutas y la rama; `summary` usa
   `scripts/viewtv_release_0013_summary_safe.py` para mostrar
   solo banderas no secretas. `config --quiet` PASS. Los dos
   servicios conservan `/data`, `/cache` y `/media:ro` cuando
   corresponde. `rollback-summary` reprodujo
   `viewtv:playback-hls-api-0012` y
   `viewtv:verificacion-compatible-worker-0012`.

## Respaldo inmediatamente anterior, con servicios detenidos

Los contenedores `viewtv-worker-1` y `viewtv-api-1` se
detuvieron **en ese orden**; el frontend y Jellyfin siguieron
ejecutándose. Antes de cambiar SQLite se generó:

- `/home/viewtv/viewtv-backups/api-resultados-predeploy-20261121-232539.db`
  SHA-256 `1b3e84dac811c1d2f39badc7110e7f01a0445f05b7d245260b157d898d0c4f79`.
  Copia consistente, `PRAGMA integrity_check=ok`,
  `foreign_key_check=0`, esquema 0012.
- `/home/viewtv/viewtv-backups/release-0013-preprod-20261121-232539.tar.gz`
  SHA-256 `257412c42d9c17a7df9c15bf6c89a5272b2974434d27a515705fd5c439f39636`.
  Contiene copia SQLite anterior, Compose candidato, script seguro
  y documentación. `tar -tzf` y `sha256sum` verificados.
- Respaldo de preparación de código/docs:
  `/home/viewtv/viewtv-backups/preparacion-release-0013-20261121-232555.tar.gz`
  SHA-256 `49e952f3c10351c6ec129091a7c2bff5737e35350b3188370308d93d90370afc`,
  `tar -tzf` verificado.

Las scripts nuevos no tenían versión previa; se incluyeron las
versiones parciales iniciales en el archivo de preparación antes
de modificar su control de publicación.

## Despliegue y controles posteriores

Se ejecutó `bash scripts/viewtv_release_0013_compose_safe.sh up-api`
con API y worker parados: solo se recreó API usando
`docker compose up -d --no-deps --no-build --force-recreate api`.
El inicio hizo Alembic `upgrade head`; API saludable, salud HTTP OK,
revisión real `0013_cola_organizacion`.

Después se ejecutó `up-worker` con API healthy y SQLite 0013,
recreando solamente worker con los mismos flags de seguridad.
En modo lectura, la base real pasó integridad, FK y recuentos
históricos (2,3,7,2,64); `organizacion_pendientes=0`.
`python -m worker.organization_windows_cli status` devuelve
`{"estado":"deshabilitado"}` en la API nueva.
El smoke read-only `scripts/viewtv_release_smoke_0012_readonly.py`
dio `SMOKE_READONLY=10_PASS`: frontend, proxy, perfiles, sesiones
protegidas y Jellyfin. Esta evidencia no sustituye un nuevo
ensayo visual ni una publicación automática.

## Reversión preparada (NO ejecutada)

No se necesitó revertir: los dos servicios siguen saludables.
Si 0013 falla antes de tener trabajos persistidos:
detener **worker y API** de forma ordenada; comprobar el estado
de la cola y las copias verificadas; ejecutar Alembic
`downgrade 0012_inicio_torrent` únicamente con ambos parados
y después verificar integridad, FK y versión.
Restaurar las imágenes/overrides 0012 identificados por
`rollback-summary`, recreando **api** y **worker** por separado
con `--no-deps --no-build --force-recreate`.
Jamás sustituir la base real a ciegas: si existen trabajos 0013
persistidos, el downgrade se niega explícitamente.
Conservar el respaldo 0012. No usar `docker compose down -v`.

## Próximo bloqueo funcional

Falta instalar un publicador Windows con **identidad controlada**,
permisos locales revisados, aprobación limitada a la futura
`download_id > 2` y comprobación de su comunicación con API 0013.
LocalSystem pudo acceder a Docker en un ensayo, pero dispone de
privilegios amplios; eso **no demuestra aislamiento del broker**.
No autorizar modo general ni manipular un torrent ajeno para obtener
una ID de prueba. El usuario tendrá que seleccionar una segunda
película apropiada en la aplicación para la prueba de
búsqueda→selección→descarga→verificación→publicación→Jellyfin
completado→catálogo VIEWTV→reproducción.

**Comprobación posterior de preparación (21/11/2026):**
el preflight real de solo lectura Windows ha dado
`LISTO_PARA_NUEVA_SELECCION_VIEWTV_0013=SI`.
La consulta SQLite en `/data:ro` ha dado
`DESCARGAS_NUEVAS=0` para ID > 2.
Ya es seguro que el usuario seleccione una nueva película mediante
ViewTV, pero **todavía no que la publique un servicio real**
hasta obtener ID verificada y desplegar la autorización `single`.
Ver [AVANCE-PREFLIGHT-NUEVA-PELICULA-0013-20261121.md](AVANCE-PREFLIGHT-NUEVA-PELICULA-0013-20261121.md).

PR #2 debe permanecer **OPEN y draft**, sin merge ni cierre.
Ninguna tarea del backlog de cosmética o indexadores se reabre.
