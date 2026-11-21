# VIEWTV — publicación automática futura con tarea Windows limitada

**22/11/2026 · rama `viewtv-seguimiento-descargas-0012` · PR #2 OPEN/DRAFT.**
Worktree exclusivo: `/home/viewtv/projects/viewtv-broker-0013-20261119`.

## Alcance entregado

**Automatización periódica configurada y activa**, sin Windows Service
bajo LocalSystem. Una tarea programada denominada
`VIEWTV - Publicador automatico 0013` ejecuta el publicador bajo la
**misma cuenta interactiva de Windows, pero con token LIMITED/no
elevado**, cada cinco minutos y al iniciar sesión. Requiere que
el usuario tenga una sesión de Windows iniciada y Docker Desktop
disponible; **no es un servicio desatendido antes del login**.
No se creó contraseña ni una nueva cuenta de Windows.

API `viewtv:auto-publicador-api-0013` usa:
`VIEWTV_WINDOWS_PUBLICATION_MODE=general`,
`VIEWTV_WINDOWS_PUBLICATION_AFTER_ID=3`,
`VIEWTV_WINDOWS_PUBLICATION_GENERAL_APPROVED=true`.
La política privada de Windows coincide:
`{"mode":"general","after_id":3,"allowed_download_id":null}`.
Esto excluye estrictamente las descargas históricas **#1, #2 y #3**.
La próxima elegible será **ID #4 o posterior** siempre que ViewTV
la haya registrado, completado y verificado. No autoriza publicar
medios que no sean propiedad de la descarga de ViewTV ni
torrents ajenos.

Worker `viewtv:release-0013-worker-candidate` conserva organización
`false` y publicación `disabled`, auto-descarga `true`,
verificación `true`, envío e inicio de torrents manuales `false`.
Los contenedores frontend/Jellyfin/FlareSolverr NO fueron recreados.
La única API recreada sigue healthy y conserva HLS de la segunda
película. SQLite productiva sigue en `0013_cola_organizacion`.

## Ciclo automático

1. La tarea exige usuario NO elevado, ACL privada de Windows,
   rutas NTFS sin redirección y congruencia entre política host/API.
   Si falla, termina con código 2; no ignora el control.
2. `scripts/viewtv_windows_publicador_0013.ps1 -Mode Once` utiliza
   CLI de autoridad en API, `claim` con `BEGIN IMMEDIATE`,
   lease y cotejo de torrent verificado. No se publican carpetas
   previas ni se sobrescribe ningún título.
3. El host Windows crea enlaces duros NTFS conservando el original,
   mueve una carpeta staged en la misma unidad y guarda el diario
   privado; confirma la organización y solicita escaneo Jellyfin.
4. Nuevo comando `python -m worker.organization_windows_cli sync`,
   solo autorizado en modo general, comprueba que Jellyfin responde
   con biblioteca mínima y ejecuta `synchronize_catalog`, la
   sincronización transaccional ya usada por API. Se repite cada
   ciclo, de modo que un escaneo asíncrono completado entre pasadas
   terminará reflejándose en el catálogo ViewTV.
5. La tarea guarda **solo metadatos sin secretos** en
   `C:\VIEWTV\publicador\journal\tarea-periodica-0013-estado.json`,
   con estado, resultado `publicacion`, resultado de catálogo y UTC.
   Ninguna decisión de publicación depende de ese registro.
   `LastTaskResult=0` es el control de la tarea.

No se guardan PIN, `.env`, tokens Jellyfin ni contraseñas.
El acceso a Docker desde la cuenta de Windows sigue siendo potente;
**RunLevel Limited no equivale a aislamiento por SID independiente**
ni elimina los privilegios que Docker Desktop pueda conceder. Se
mantiene esa limitación expresamente documentada.

## Comprobaciones reales

- La primera tarea de ensayo ejecutada como `Limited`
  devolvió `SONDEO_LIMITADO_OK`, no elevada, con acceso Docker,
  ACL/NTFS revisadas y medios en `/media:ro`. No se reclamó cola.
- La tarea de producción se registró **deshabilitada** con
  `LogonType=Interactive`, `RunLevel=Limited` y activadores:
  `AtLogOn` y repetición `PT5M` por el programador de Windows.
- Hubo un problema de preflight **detectado antes de la activación**:
  dot-source del publicador alteraba el parámetro PowerShell
  `$Mode` del lanzador y saltaba una línea de comando, iniciando
  PowerShell sin argumentos. Se detuvieron solo los procesos de prueba
  propios, se guardó respaldo, se preservó `$requestedMode` y se
  corrigió la invocación de proceso/CLI en una línea. El preflight
  limitado volvió a pasar con `LastTaskResult=0`.
- La API candidata se verificó con SHA-256 del mismo código fuente
  en imagen y repo, Alembic 0013, y solo se recreó
  `viewtv-api-1` usando `docker compose up -d --no-deps --no-build
  --force-recreate api`. API CLI real:
  `{"estado":"listo","modo":"general","after_id":3,
  "allowed_download_id":null}`. Smoke read-only **10/10 PASS**.
- Política host aprobada con sustitución atómica y copia de su
  antigua versión `single` en
  `C:\VIEWTV\publicador\aprobacion.antes-general-20261122-004237.json`.
  No se borró ni modificó el diario de la película #3.
- La primera ejecución de la tarea real terminó `0` con
  `sin_trabajos` y `catalogo_sincronizado`, sin ID nueva.
  La siguiente detectó un problema **solo en la telemetría**:
  el token limitado no podía usar `File.Replace` sobre el registro.
  Se demostró mediante un sandbox separado cuyo resultado fue
  `SANDBOX_REPLACE_FAIL=MethodInvocationException`.
- Tras respaldo y con la tarea deshabilitada, se cambió el registro
  por `File.WriteAllText` sobre el archivo de estado PROPIO
  (ACL privada, reparse rechazado). Este archivo no es de medios,
  journal de publicaciones ni autoridad. Las dos siguientes
  ejecuciones consecutivas terminaron **código 0**,
  `publicacion=sin_trabajos`,
  `catalogo=sincronizado`, con sello UTC actualizado y sin
  errores ni movimientos de media.
- Las tres tareas temporales de test se retiraron de
  Task Scheduler; se conservaron únicamente sus pruebas
  documentadas y los archivos sandbox privados de auditoría.
  **Solo queda habilitada la tarea real**.
- Pruebas Python: **896/896 PASS**, 2 warnings de deprecación,
  y `ruff check` PASS. Nuevas regresiones del comando `sync`
  en modo general, rechazo de modo single/disabled y rechazo
  de Jellyfin vacío antes de escribir. Tres pruebas HLS 0013
  anteriores siguen en suite.
- En ningún momento se pidió un torrent nuevo de prueba:
  último estado conocido `DESCARGAS_NUEVAS=1` para ID>2,
  siendo solo #3 `organizada`. **No afirmar una publicación
  #4 realmente realizada ni una reproducción visual nueva.**

## Copias verificadas

- `/home/viewtv/viewtv-backups/publicador-auto-general-pre-20261122-003621.tar.gz`
  SHA-256 `672a3d896c70e113b88d21a1b32e6dc8b3224cc7412370f004c12fb0d80f11b6`;
  contiene código anterior, política `single` Windows y planes.
- `/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-004055.db`
  SHA-256 `72a9007f1867e23f95b8cf649c24f1e44bd8d4c88e933379e5aa29226001149b`,
  SQLite online backup, integridad y FK OK,
  revisión 0013, #3 `organizada`.
- `/home/viewtv/viewtv-backups/publicador-auto-predeploy-20261122-004055.tar.gz`
  SHA-256 `bfd1c19987b52b22eeddab3fd9837f58174e7f85964b6a1f95636c05a7284d00`,
  incluye copia SQLite y scripts de predeploy.
- `/home/viewtv/viewtv-backups/tarea-periodica-lanzador-fix-pre-20261122-004500.tar.gz`
  SHA-256 `fedca9e1d729c1c58fcf6a5646e1ca78d3083a6c0b2d63c6cc576e276b9bf8db`.
- `/home/viewtv/viewtv-backups/tarea-periodica-log-pre-20261122-005000.tar.gz`
  SHA-256 `03d18a4028272b0ca4a1de7378f546eb0c5374b87329b8cd389bf9e7ac22d4de`.
- `/home/viewtv/viewtv-backups/docs-auto-hito-pre-20261122-005200.tar.gz`
  SHA-256 `6fa4b2438bd17f0820fb53c5310a3197812c27418ce5f75a5d15be219d6ec858`.

Todos los tar fueron comprobados con `tar -tzf` y `sha256sum`.
No se restauró SQLite ni se tocó material `.bak` del usuario.

## Reversión operativa sin destruir la biblioteca

Si la tarea devuelve fallo continuado, en Windows:

```powershell
Disable-ScheduledTask -TaskName 'VIEWTV - Publicador automatico 0013'
```

Después, desde la worktree autorizada en WSL:

```bash
bash scripts/viewtv_compose_publicacion_automatica_0013.sh rollback
```

Esto recrea únicamente API HLS 0013 anterior, con publicación
`disabled`; no revierte la SQLite ni altera descargas. Confirmar
`docker exec viewtv-api-1 python -m worker.organization_windows_cli status`
`deshabilitado`. La política Windows local podrá restaurarse
**solo después** de detener la tarea y comprobar que API está
deshabilitada, usando la copia previa protegida de
`aprobacion.antes-general-20261122-004237.json`. Conservar
ese respaldo y el diario; nunca ejecutar `docker compose down -v`,
borrar `.bak`, reinstalar bajo LocalSystem ni tocar torrents ajenos.

## Siguiente comprobación necesaria

Que el usuario seleccione la **tercera película** desde ViewTV, con
derecho a descargarla, y que reciba una ID nueva (debería ser #4).
Después verificar en **solo lectura** el ciclo completo:
descarga → verificación → tarea periódica Windows → enlace NTFS →
confirmación SQLite → escaneo Jellyfin terminado →
sincronización ViewTV → carátula → reproducción visual/audio.
Hasta entonces, el sistema está **configurado y funcionando en
vacío**, pero la entrega automática de una película nueva
**aún no tiene prueba E2E real**.
