# VIEWTV — reproducción confirmada y prueba NTFS del publicador 0013

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Plan maestro:** `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`.

## Hito 1 — reproducción HLS confirmada por el usuario

El usuario confirmó expresamente: «sí, ya se ve la peli», y
reiteró que se ve bien. Esto cierra la prueba visual pendiente de
«Nadie 2» tras la corrección del `ref={videoRef}`.
No se volvió a modificar HLS, Jellyfin ni el MKV.
La confirmación visual no demuestra reproducción de dos horas sin cortes
ni sustituye una prueba de fluidez prolongada.

## Hito 2 — qué bloqueo se intentó desbloquear

La publicación de «Nadie 2» fue puntual. La aplicación todavía
necesita una **autoridad Windows autónoma**, con
`download_id`, aprobación, lease, infohash, diario y publicación NTFS
durable, para cualquier película futura. Es el bloqueo prioritario
frente a tareas cosméticas o indexadores Jackett 404 del backlog.

Antes de tocar código se observó en modo lectura `git status`,
`git log --oneline -10`, `docker ps` y
`curl -s localhost:8000/health`: rama limpia en `27bff27`,
API/frontend healthy, worker/Jellyfin en marcha, salud HTTP OK.
No se confundió esa salud con un circuito de descarga/publicación
verificado.

## Código y evidencia en este avance

- `scripts/viewtv_windows_publicador_0013.ps1` admite cargar
  funciones sin ejecutar publicación (entrada `Library`) para
  pruebas completamente separadas bajo `C:\Users\Public`.
  Se corrigió un defecto real: `Split-SafeRelative` devolvía un
  array anidado, que causaba rechazo de todo destino de película;
  devuelve ahora los segmentos de ruta correctos.
- `scripts/test_viewtv_windows_publicador_0013_sandbox.ps1`
  crea únicamente un directorio marcado con GUID, y un vídeo ficticio;
  simula decisiones de la autoridad (no usa qBittorrent, claves,
  Jellyfin, Docker ni SQLite reales); comprueba enlace duro NTFS,
  `Directory.Move`, fuente intacta, ausencia de `.url`, diario,
  solicitud simulada de escaneo, rechazo de colisión y
  recuperación tras una confirmación perdida **sin segunda publicación**.
  El ensayo pasa y borra solamente el sandbox marcado creado por él.
- `worker/organization_windows_cli.py` expone `status` de
  solo lectura: informa del modo aprobado y el corte histórico solo
  si el esquema es 0013. No reclama una descarga ni publica.
  `Preflight` del publicador compara ambas aprobaciones (Windows/API)
  y rechaza cualquier discrepancia.
- El bucle `Loop` del publicador deja de ignorar excepciones:
  ante fallo bloqueante termina con código no-cero y mensaje de estado
  **sin ruta, PIN, infohash ni secretos**. El servicio no debe simular
  funcionamiento sano mientras falle.
- `scripts/viewtv_instalar_publicador_windows_0013.ps1`
  exige ahora el parámetro adicional de aprobación de Control de
  aplicaciones; el resto de requisitos de copia y autorización por ID
  permanecen. No se instaló ni inició el servicio de producción.
- `backend/tests/test_organization_windows_service_status.py`
  verifica los estados de preflight con políticas ficticias, sin
  conexión a SQLite real.

## Bloqueo real encontrado: Windows Control de aplicaciones

Para verificar que el Windows Service Control Manager podía ejecutar
un proceso propio y acceder a Docker como `LocalSystem`, se
construyó una prueba con servicio temporal **distinto** del publicador,
contenida en `C:\Users\Public\viewtv-svc-probe-<GUID>`.
El servicio de prueba registró correctamente su ejecutable compilado
pero el comando `sc.exe start` devolvió:

`StartService ERROR 4551: Una directiva de Control de aplicaciones bloqueó este archivo.`

Esta evidencia **no demuestra acceso ni denegación a Docker desde
LocalSystem**: Windows ni siquiera permitió iniciar el ejecutable.
No se probaron otras ubicaciones, no se alteraron ni eludieron las
directivas, y no se tocó la carpeta `C:\VIEWTV\media`.

Tras la prueba se comprobaron `Get-Service ViewtvProbe*`,
`Get-Service ViewtvPublicador0013` y carpetas con marcador de
prueba bajo `C:\Users\Public`: **sin resultados residuales**.
El registro temporal SCM se retiró y el directorio creado se eliminó
solo tras comprobar GUID y marcador. No existe publicador activo.

**Decisión:** no desplegar una API/worker 0013 habilitados para
publicación ni instalar un servicio real hasta que un administrador
autorice expresamente, conforme a la política de Control de
aplicaciones, la ejecución del servicio. No intentar sortear la
directiva mediante otra ruta, nombre o ejecutable.

## Respaldos anteriores a cualquier edición

- `/home/viewtv/viewtv-backups/publicacion-0013-integracion-pre-20261121-230243.tar.gz`
  SHA-256 `d37150af553247b85291a7f167d4391bb583800f5375db1b87e2b8a72b969267`.
  Copia previa de plan/documentación, cola, CLI, publicador,
  instalador, candidatos de despliegue; `tar -tzf` comprobado.
- `/home/viewtv/viewtv-backups/publicador-scm-test-pre-20261121-230533.tar.gz`
  SHA-256 `a250fb451de3d538d1777375e1a7da8ea11164dff9658cbf59f6598de618c774`.
  Copia de ambos scripts de ensayo y publicador antes de ajustes;
  `tar -tzf` comprobado.
- Los nuevos scripts de ensayo y la nueva prueba Python no tenían
  versión previa al crearse.

**SQLite productiva intacta**: continúa en 0012. No se alteró
qBittorrent, biblioteca, usuarios, PIN, archivos `.bak`, ni
parámetros de descarga automática `AUTO_DOWNLOAD_AFTER_ID=1`.

## Pruebas aún NO realizadas y siguiente paso real

1. Un administrador del equipo debe verificar/aprobar la ejecución
   del servicio conforme a Control de aplicaciones; no basta con
   permitirlo en el texto de un chat. Hasta entonces no instalarlo.
2. Ensayar el propio Windows Service y su acceso a la autoridad
   Docker en laboratorio; si no puede acceder, detener y resolver
   por un canal expresamente permitido, **sin eludir políticas**.
3. Inmediatamente antes del primer despliegue real: respaldo SQLite
   consistente y configuración, `sha256sum`, `tar -tzf`,
   `PRAGMA integrity_check`, `PRAGMA foreign_key_check`;
   simular `0012→0013→0012` sobre clon fresco y reversión.
4. Emparejar API y worker 0013, activar publicación **solo para una
   descarga ID > 2** validada y autorizada; nunca reutilizar #2 ni
   tocar torrents ajenos. Descargar y verificar una segunda película,
   publicar sin script puntual, conciliar, finalizar escaneo Jellyfin,
   comprobar carátula/identidad y catálogo VIEWTV, reproducir.
5. Solo después de ese ensayo aprobado pasar de `single` a
   `general`, desplegar gradualmente y monitorizar.
   **PR #2 permanece en borrador**, no cerrar ni fusionar.

**Rollback de este avance:** no hay despliegue real que revertir.
Los cambios de código pueden revertirse con un nuevo commit sobre la
misma rama, sin `reset --hard` ni `git clean`. Conservar respaldos.
Si algún día se instala el servicio, detenerlo antes de reconfigurar
API/worker; mantener intacto el diario y las películas publicadas.
La reversión SQLite futura debe ensayarse primero en copia: Alembic
rechaza el downgrade si existen trabajos 0013 persistidos.

## Estado de pruebas automatizadas

La suite backend completa y el análisis estático se ejecutaron
sobre código montado **solo lectura** en un contenedor efímero, sin
archivos ni claves reales: **889/889 PASS**, 2 warnings de deprecación
preexistentes, `ruff check` PASS. El sandbox nativo Windows de
publicación pasó; el ensayo del servicio Windows se detuvo por Control
de aplicaciones (4551), **sin considerar esto prueba de funcionamiento**.
Se construyeron de nuevo las dos imágenes candidatas API/worker 0013;
cola, CLI y migración tienen SHA-256 idénticos en ambas y
`alembic heads` = `0013_cola_organizacion`.
No se han desplegado ni migrado la SQLite real.

**Regla de prioridad:** los errores 404 y estado del indexador
permanecen en `docs/BACKLOG.md` sin intervenir. Nada de cosmética,
cierre de sesión, animaciones, rendimiento o endurecimiento adicional
que no desbloquee el circuito principal.
