# VIEWTV — candidato del publicador Windows 0013, SIN despliegue

Fecha: 21/11/2026. Rama exclusiva: `viewtv-seguimiento-descargas-0012`.
Plan obligatorio: `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`.

## Bloqueo que se aborda

Una película ya se descargó, se verificó y llegó a Jellyfin con carátula:
«Nadie 2» (descarga #2). Pero su publicación fue un script puntual.
La aplicación **no publica automáticamente películas nuevas**.
Este avance prepara la conexión de la cola 0013 a una autoridad Windows
independiente del proceso del worker, sin montar las bibliotecas con
permisos de escritura en Docker. No declara ese objetivo completado.

La reproducción visual de «Nadie 2» tampoco está confirmada todavía
por el usuario después del arreglo de `ref={videoRef}`. La indicación
«vale, continua» autoriza proseguir preparativos, no acredita imagen/audio.

## Implementado en la rama, deshabilitado

- `backend/app/organization_queue.py`: reclamación `BEGIN IMMEDIATE`
  limitada opcionalmente a una ID y a un corte histórico `min_download_id`.
  Ninguna descarga excluida consume lease ni intentos.
- `worker/organization_windows_authority.py`: modo deshabilitado por
  defecto; `single` exige ID nueva explícita; `general` exige
  aprobación específica y corte duradero. Rechaza lease vencido, estado
  no verificado, hash/etiqueta incorrectos, rutas ajenas, múltiples vídeos
  y publicaciones de series en la primera fase. Preparación con rutas
  relativas; ignora archivos `.url` sin publicarlos.
- `worker/organization_windows_cli.py`: operaciones acotadas `claim`,
  `prepare`, `verify-source`, `renew`, `confirm`, `review`, `scan`
  para la candidata de API 0013. Exige esquema Alembic 0013.
  Las consultas de identidad qBittorrent son GET; el comando no copia
  medios. `scan` solicita escaneo, no acredita catálogo visible.
- `scripts/viewtv_windows_publicador_0013.ps1`: bucle Windows separado;
  raíces fijas de NTFS `C:\VIEWTV\media`, comprobación de ACL privadas y
  de reparse points, aprobación local por ID, lectura de cola 0013,
  validación previa de torrent y lease, diario `CreateNew`/WriteThrough,
  `CreateHardLinkW`, y `Directory.Move` sin reemplazar destino.
  En resultado ambiguo conserva journal/staging y no hace otra publicación.
  La reconciliación contrasta origen y manifiesto guardado en el diario.
  Reintenta solicitud de escaneo para publicaciones confirmadas sin recopia.
- `scripts/ViewtvPublicadorServicio0013.cs`: envoltorio nativo del
  Windows Service Control Manager que ejecuta el bucle de PowerShell
  independientemente del worker de Docker.
- `scripts/viewtv_instalar_publicador_windows_0013.ps1`: instalación
  explícita y detenida, con comprobación de respaldo SHA-256/tar,
  único ID y ACL; comandos de estado, parada y retirada del registro.
  **No se ha ejecutado `InstallSingle`.** `Status` devuelve
  `SERVICIO_NO_INSTALADO`.
- Candidatas API y worker actualizadas desde las imágenes productivas
  **actuales** HLS y verificación compatible, con código/esquema
  emparejados y publicación deshabilitada de entrada; API con lectura
  multimedia `/media:ro`. Override adicional para una sola ID posterior
  al corte **2**. No se modificó `worker/main.py` ni se activó
  `VIEWTV_ENABLE_ORGANIZATION`.

## Evidencia y límites

- Estado observado al comenzar: rama correcta limpia en `af1b9f1`,
  API y frontend healthy, worker activo, Jellyfin activo; `/health`
  respondió `estado=ok`. Ninguno de estos healthchecks acredita el
  circuito de película.
- Prueba de cola una ID + política Windows + metadatos sintéticos:
  **18/18 PASS** en contenedor desechable, sin acceso a datos de usuario.
- `ruff check` para módulos nuevos y cola: **PASS**.
- El publicador y el instalador PowerShell se analizaron con
  `System.Management.Automation.Language.Parser`: **sin errores**.
- El envoltorio C# para Windows Service compiló con csc.exe local:
  **PASS**, pero no se ha instalado ni probado bajo cuenta de servicio.
- Suite completa backend con todo el árbol de código en montaje de
  solo lectura en contenedor desechable: **886/886 PASS** en 55,29 s,
  solo 2 avisos de deprecación preexistentes. No se montó SQLite real
  ni biblioteca del usuario, y no hubo comunicación con qBittorrent.
- Primer intento de suite completa incompleto por **montaje de test**
  (no incluía `/opt/viewtv/scripts`): error en colección de
  `test_release_diagnostics_readonly.py`, no evidencia de fallo funcional.
- Ambas imágenes candidatas 0013 se construyeron desde las imágenes
  actuales HLS y verificación (`docker build --pull=false`) sin recrear
  contenedores productivos. Sus archivos `models.py`, `organization_queue.py`,
  `organization_windows_cli.py` y migración 0013 presentan SHA-256 idénticos
  entre API y worker. `alembic heads`: `0013_cola_organizacion` en ambas.
- El preflight `docker compose config --quiet` no pudo hacerse desde
  este worktree porque no tiene archivo `.env`; no copiar credenciales
  desde producción ni inventar valores.

### Sin comprobar todavía

La prueba visual de «Nadie 2» (imagen, audio y duración), el arranque
efectivo del servicio Windows, permisos/ACL y acceso a Docker Desktop
bajo su identidad de servicio, el despliegue simultáneo de API y worker
0013, la migración SQLite de producción, el escenario de caída real,
la organización automática de una segunda película, el escaneo
**completado**, ficha con carátula y reproducción de esa segunda película.
Los ensayos anteriores de sandbox no sustituyen estas pruebas. La
implementación candidata no debe activarse hasta superar los controles
en una biblioteca de prueba, especialmente el confinamiento Windows.

## Respaldo previo verificado

1. `/home/viewtv/viewtv-backups/publicador-pre-20261121-224344.tar.gz`
   SHA-256 `a07c74635ab6bff0c2fb9c38a0ca43f6c287d622df85415c41a6d475e463a205`.
   Código de cola, plan, backlog, publicadores anteriores; lista
   `tar -tzf` comprobada.
2. `/home/viewtv/viewtv-backups/publicador-build-pre-20261121-225351.tar.gz`
   SHA-256 `62d08cd769860feff57478444846209cdfaa66f3e27ee76ded422a9e5f7376a6`.
   Dockerfiles y Compose candidatos anteriores; `tar -tzf` comprobado.

**No se escribió ni respaldó de nuevo la SQLite productiva en este
avance porque no se ha leído ni modificado; se exige copia consistente,
integrity/FK y hash inmediatamente antes de la futura migración.**
No se han movido medios ni tocado torrents ajenos.

## Camino de despliegue, prueba y reversión (PENDIENTE, no ejecutar aún)

1. Confirmar visualmente HLS tras Ctrl+F5. Seleccionar una segunda
   película apropiada y autorizada, sin recuperar la descarga #2.
2. Antes de cambiar imágenes, esquema o servicio: respaldo online
   consistente de SQLite y configuración; `sha256sum`, `tar -tzf`,
   `PRAGMA integrity_check` y `PRAGMA foreign_key_check` sobre la copia.
   Simular `0012→0013→0012` en clon y comprobar cuentas y contenidos.
3. Validar API/worker candidatas con mismo código y esquema; migrar
   SQLite una sola vez a 0013, desplegar ambos servicios coordinados,
   mediante `docker compose up -d --no-deps --no-build --force-recreate`
   **solo** para el servicio indicado (y sin `down -v`). El modo
   de publicación sigue `disabled` durante el despliegue base.
4. Preparar aprobación local para una sola descarga **ID > 2**.
   Instalar servicio Windows detenido y ensayar control `Preflight`
   bajo su identidad, ACL, permisos y respuesta de autoridad; después
   habilitar únicamente esa ID. No usar general aún.
5. Observar descarga, verificación, journal, publicación Windows sin
   script puntual, escaneo Jellyfin **terminado**, sincronización
   VIEWTV, carátula y reproducción visual. Solo entonces aprobar
   modo `general` con corte histórico y desplegar gradualmente.
6. **Rollback preparado, no ensayado en producción:** detener
   `ViewtvPublicador0013`; deshabilitar `VIEWTV_WINDOWS_PUBLICATION_MODE`
   en API; conservar diario, staging, carpeta publicada y torrents;
   respaldar estado. Revertir API/worker conjuntamente a las imágenes
   anteriores solo tras comprobar compatibilidad de esquema y estado.
   La migración `0013→0012` puede rechazar trabajos persistidos;
   simular la reversión en copia y no eliminar esos trabajos ni forzar
   downgrade en producción. La retirada del servicio con `Unregister`
   conserva datos, no borra carpetas ni archivos `.bak`.

El PR #2 permanece abierto en **borrador** y no puede cerrarse ni
fusionarse sin autorización expresa del usuario.

## Secundarios aplazados

`docs/BACKLOG.md` ahora enumera por separado enlaces Jackett 404
y estado administrativo del indexador. Ninguno se ha investigado,
modificado ni reabierto. Se mantienen allí cierre de sesión,
cosmética, rendimiento, endurecimientos y demás mejoras.
