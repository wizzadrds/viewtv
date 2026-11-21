# VIEWTV — preflight real 0013 para la segunda película

Fecha: 21/11/2026. Rama: `viewtv-seguimiento-descargas-0012`.
Entorno: WSL Ubuntu 24.04 + PowerShell Windows 11, equipo
LAPTOP-V2QSMC01, worktree autorizado
`/home/viewtv/projects/viewtv-broker-0013-20261119`.

## Decisión operativa

**LISTO para que el usuario cree una nueva solicitud de película
desde la PWA ViewTV.** No se ha instalado el servicio publicador ni
se ha autorizado ninguna ID nueva. La publicación Windows permanece
desactivada y fallará cerrada hasta que exista una descarga real
verificada y se habilite exclusivamente esa ID.
No se debe descargar la película manualmente fuera de ViewTV;
el usuario debe elegir un resultado válido que tenga derecho
a obtener desde la propia aplicación.

## Evidencia: preflight Windows real de solo lectura

Nuevo `scripts/viewtv_preflight_siguiente_descarga_0013.ps1`,
ejecutado en Windows PowerShell 5.1 con código de la rama autorizada.
No crea directorios, no lee archivos de película,
no cambia ACL, no instala el servicio y no reclama la cola SQLite.

Resultado real (salida sin secretos):

```text
RUTAS_NTFS=OK_SOLO_METADATA
API_WORKER_0013=OK
PUBLICACION_AUN_DESHABILITADA=OK
PUBLICADOR_WINDOWS_NO_ACTIVO=OK
LISTO_PARA_NUEVA_SELECCION_VIEWTV_0013=SI
```

Concretamente ha comprobado:
- `C:\VIEWTV`, raíz multimedia, descargas temporales y Peliculas
  son directorios sobre NTFS sin atributo ReparsePoint.
- API `viewtv:release-0013-api-candidate` healthy,
  worker `viewtv:release-0013-worker-candidate` activo.
  Ambas reportan `0013_cola_organizacion` en Alembic;
  ambas montan `/media` en **solo lectura**.
- `VIEWTV_WINDOWS_PUBLICATION_MODE=disabled` en API/worker;
  CLI `python -m worker.organization_windows_cli status`
  devuelve únicamente `deshabilitado`, sin escribir SQLite.
- `VIEWTV_ENABLE_ORGANIZATION=false`,
  `VIEWTV_ENABLE_AUTO_DOWNLOAD=true`,
  `VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1`,
  `VIEWTV_ENABLE_DOWNLOAD_VERIFICATION=true`,
  `VIEWTV_ENABLE_DOWNLOAD_START=false`,
  `VIEWTV_ENABLE_TORRENT_SUBMIT=false`.
- No hay un `ViewtvPublicador0013` ejecutándose.

## Evidencia de IDs: sin leer nombres ni torrents

Nuevo `scripts/viewtv_descarga_0013_estado_readonly.py`.
Ejecutado en contenedor efímero, sin red, montando el volumen
`viewtv_viewtv_data` como `/data:ro` y el script como
bind en solo lectura; abre SQLite con `mode=ro` y
`PRAGMA query_only=ON`, exige esquema 0013 y solo imprime
identificador, estado, progreso y organización de descargas con
**ID superior a 2**. No muestra título, torrent hash, ruta,
usuario, PIN ni credenciales.

Resultado:

```text
DESCARGAS_NUEVAS=0
```

No se insertaron descargas ni se seleccionó película automáticamente.
No afirmar que un torrent futuro exista ni que esté verificado.

## Cómo retomar cuando el usuario seleccione una nueva película

1. El usuario selecciona una **nueva película autorizada en ViewTV**;
   el worker actual conserva la descarga automática. Basta que
   avise «ya está seleccionada». No necesita identificar el hash.
2. Repetir el comprobador de IDs (solo lectura). Elegir la ID
   **real** de la nueva descarga (nunca #1, #2 ni una ajena);
   observar `completada`, `verificada` y
   `organizacion_estado=pendiente` sin cambiar torrent ni archivo.
   No empezar un publicador sobre descarga incompleta.
3. Antes de cambiar el servicio/API: respaldo consistente SQLite
   nuevo y verified sha/tar; validación en clon y rollback.
   Utilizar la configuración `single` de
   `deploy/compose.publicacion-una-id-0013.yaml` únicamente
   con esa ID, con worker organización deshabilitada.
4. Comprobar aprobación Windows para la **misma ID**,
   servicio SCM detenido, ACL del diario, separación de permisos,
   fuente y plan coincidentes con la descarga y leasing.
   Solo arrancar el publicador ya verificado. **No utilizar
   modo general, ni LocalSystem como supuesta frontera de
   confianza independiente**.
5. Seguir origen → publicación NTFS → confirmación en cola →
   escaneo de Jellyfin completado → catálogo ViewTV →
   prueba de reproducción visual informada por el usuario.
   Si algo falla, detener y conservar diario, película original
   y respaldo; no repetir escrituras ambiguas.
6. En todo momento, mantener PR #2 OPEN y draft; no fusionar.

El preflight prueba que la *selección* de una descarga nueva es
segura con el publicador aún desactivado; **no prueba todavía
publicación desatendida**, independencia real de SID/ACL,
carátula de la segunda película ni finalización de Jellyfin.

## Respaldo verificado

Antes de añadir scripts y modificar informes existentes:

`/home/viewtv/viewtv-backups/preflight-descarga-0013-pre-20261121-234530.tar.gz`

SHA-256
`f627b5ef4db313ae85ff44b5ca45be75d2b88599f39780f2a3b581199c6d6398`.

`tar -tzf` verificó el contenido:
`docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`,
`docs/BACKLOG.md`,
`docs/AVANCE-RELEASE-0013-SIN-PUBLICACION-20261121.md`,
`scripts/viewtv_instalar_publicador_windows_0013.ps1`,
`scripts/viewtv_windows_publicador_0013.ps1`.

Los dos scripts de preflight/estado y este informe son **nuevos**,
por lo que no había versión anterior que respaldar.
No se modificaron SQLite ni datos de producción en este avance.
