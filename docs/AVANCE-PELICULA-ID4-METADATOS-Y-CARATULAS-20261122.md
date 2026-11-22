# VIEWTV — descarga #4 automática, metadatos y carátulas

**Fecha:** 22/11/2026 (Europe/Madrid). **Rama autorizada:**
`viewtv-seguimiento-descargas-0012`.
**Worktree:** `/home/viewtv/projects/viewtv-broker-0013-20261119`.
**PR #2:** conservar OPEN/DRAFT sin fusionar.

## Incidencia y resultado

El usuario eligió una **tercera película** en ViewTV y primero no la
encontró en el catálogo; segundos después confirmó que aparecía
**sin carátula ni otros datos visuales**. La identidad de la nueva
descarga es **#4** (nunca #1/#2/#3).

La tarea de Windows `VIEWTV - Publicador automatico 0013`,
ejecutada a las **01:09:35**, finalizó con `LastTaskResult=0`.
Su telemetría de esa ejecución registró
`publicacion=publicada` y `catalogo=sincronizado`; el journal
privado contiene `download-4.json` y `scan-4.ok`.
La SQLite 0013, inspeccionada **solo lectura**, confirmó:
`ID=4 DESCARGA=completada PROGRESO=100.0%
VERIFICACION=verificada PUBLICACION=organizada`.
Los cinco contenedores se mantenían en marcha y saludables
donde aplica. No se ha repetido la descarga, reclamado el lease
ni movido otro vídeo.

**Causa de las carátulas:** Jellyfin completó su enriquecimiento
de metadatos **después** de la primera sincronización del catálogo.
En el momento del diagnóstico:
- Jellyfin tenía **una película coincidente con #4**, con
  `ImageTags.Primary=true` y fondo `BackdropImageTags`.
- ViewTV contenía el registro para **ese mismo Jellyfin ID**
  (Medio #5), pero `imagen_portada=false`,
  `imagen_fondo=false` y título aún no actualizado.
  Por eso la coincidencia de título exacto de la solicitud
  contra el catálogo ViewTV daba 0 aun habiendo una ficha nueva.
- No era una falta real de imágenes en Jellyfin, problema de
  qBittorrent, archivo corrupto ni fallo del enlace NTFS.

## Acción controlada

Antes de escribir SQLite se realizó copia consistente de la
base de datos mediante `sqlite3.backup()` desde un contenedor
efímero sin red, con volumen origen **solo lectura**:

`/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-011238.db`

SHA-256:
`1df0afced4adb411db921ce4ede839487ae4ec714dd73b117d99f189f8a073e0`.

`scripts/viewtv_backup_id4_verifica_readonly_0013.py` verificó
`PRAGMA integrity_check=ok`,
`foreign_key_check` vacío, Alembic
`0013_cola_organizacion`, #1/#2 excluidas y
#3/#4 organizadas y sin leases. No se aplicó migración.

Se ejecutó **una vez** el comando existente, protegido por
la autoridad `general` de la API y transacción SQL:

```text
docker exec viewtv-api-1 python -m worker.organization_windows_cli sync
{"estado":"catalogo_sincronizado","elementos_procesados":4}
```

Esta operación solo sincroniza las fichas del catálogo; no
publica ni mueve multimedia y no modifica torrents.

Verificación posterior independiente:
- ViewTV Medio #5: `disponible_en_jellyfin=true`,
  `imagen_portada=true` y `imagen_fondo=true`.
- El título del catálogo ViewTV ahora coincide tanto con la
  solicitud como con el título de Jellyfin.
- **Sinopsis, año y géneros presentes**.
- Recuperación binaria real con `JellyfinClient.get_image`
  válida para Primary (2.116.987 bytes) y Backdrop
  (1.920.333 bytes).
- Proxy FastAPI privado probado mediante `TestClient`,
  con dependencia de autenticación sustituida
  **solo dentro del proceso de prueba**:
  `VIEWTV_PROXY_PRIMARY_HTTP=200`,
  `VIEWTV_PROXY_BACKDROP_HTTP=200`.
  No se cambió la autenticación de producción.
- No se recrearon contenedores ni se modificaron
  las políticas de publicación.

## Situación y limitaciones

La tarea Windows se ejecuta cada cinco minutos y
`sync` se repite incluso cuando no quedan trabajos;
eventualmente recoge metadatos enriquecidos **después**
del primer escaneo Jellyfin. El frontend refresca el catálogo
periódicamente y al regresar a la pestaña visible; si el usuario
está viendo una ficha anterior, **recargar ViewTV (Ctrl+F5)**
mostrará la versión ya actualizada.

No afirmar aún **reproducción visual de la película #4**:
el usuario solo confirmó su aparición en la biblioteca, no
que se vea y se oiga. Tampoco afirmar que la adquisición del
póster fue instantánea: hay una ventana de consistencia
eventual, con dos ciclos de cinco minutos (backend y frontend).
Un futuro refinamiento posible es avisar de «metadatos en
actualización» y reducir el tiempo de espera visible en UI
sin forzar escaneos ni reinicios de Jellyfin.

## Pruebas y respaldo de documentos

- `scripts/viewtv_incidencia_id4_catalogo_readonly_0013.py`:
  estado de ID4 y comparación inicial de fichas, sin títulos.
- `scripts/viewtv_id4_caratula_map_readonly_0013.py`:
  cotejo entre solicitud/Jellyfin ID/Medio antes y después.
- `scripts/viewtv_id4_imagenes_readonly_0013.py`:
  metadatos, imágenes reales y proxy 200, sin exponer
  imágenes, tokens, títulos ni rutas.
- `scripts/viewtv_backup_id4_verifica_readonly_0013.py`:
  copia SQLite, integridad, FK, histórico excluido.
- Antes de modificar documentación existente:
  `/home/viewtv/viewtv-backups/id4-portadas-docs-pre-20261122-011500.tar.gz`
  SHA-256
  `1f023e3d3fadfda775005d1d5af1b124ddc3bb50d8bf18b18392319a9e6fed58`;
  `tar -tzf` comprobado.
- Los cuatro scripts y este informe son **archivos nuevos**;
  no había versiones previas para respaldar.

**Próximo paso:** el usuario recarga ViewTV y confirma visualmente
póster/fondo/ficha; después puede comprobar la reproducción de #4.
No iniciar más descargas ni cambiar el modo general por esta incidencia.
