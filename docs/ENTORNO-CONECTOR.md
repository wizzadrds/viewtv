# VIEWTV — Alcance real del conector Remote Desktop Commander

Fecha de observación: 20-11-2026. Equipo identificado por el conector: LAPTOP-V2QSMC01.
Rama exclusiva de trabajo: viewtv-seguimiento-descargas-0012.
Esta comprobación no equivale a permiso para modificar producción.

## Regla persistente: desarrollo exclusivamente en Ubuntu/WSL

**Petición expresa del usuario (20-11-2026):** conectarse al apartado
Ubuntu del equipo para desarrollar VIEWTV. La terminal de Windows es la
vía de conexión y el entorno de pruebas nativas NTFS/ACL, no el lugar
donde se debe desarrollar el repositorio.

- Distribución comprobada: **Ubuntu 24.04.5 LTS**; usuario WSL: `viewtv`;
  hostname `LAPTOP-V2QSMC01`.
- Directorio de trabajo autorizado:
  `/home/viewtv/projects/viewtv-broker-0013-20261119`.
- Rama única: `viewtv-seguimiento-descargas-0012`.
- Desde Remote Desktop Commander invocar explícitamente
  `wsl.exe --distribution Ubuntu-24.04 --user viewtv --exec /bin/bash -lc 'cd /home/viewtv/projects/viewtv-broker-0013-20261119 && git status --short --branch'`.
- **No asumir el directorio inicial de WSL.** En la observación, el `pwd`
  por defecto apuntaba a un directorio del agente de Windows montado como
  `/mnt/c/Users/.../node_modules/...`, no al repositorio.
- La copia `/home/viewtv/projects/viewtv` estaba en una rama distinta y
  contenía archivos del usuario sin seguimiento; dejarla intacta.
- Se creó además `AGENTS.md` en la raíz de la rama de trabajo para
  preservar estas reglas junto al código en futuras sesiones.

### Comprobación nueva de elevación Windows

El usuario abrió una sesión PowerShell 5.1 como administrador y comprobó
el rol Administrador: **True**. De manera independiente, una invocación
PowerShell desde el propio conector Remote Desktop Commander devolvió
`CONNECTOR_ADMINISTRATOR=True` el 20-11-2026.

**Consecuencia:** ya hay elevación administrativa de Windows en la sesión
del conector; no hace falta pedir más elevación general. La lista de
comandos prohibidos del conector sigue siendo un límite separado. Esto
NO autoriza cambios en producción ni permite omitir pruebas de ACL.
Posteriormente se probaron dos cuentas temporales con SID realmente distinto;
no hay todavía servicio broker o copiador persistente.

### Respaldo de esta actualización

Antes de editar este documento se creó:
`/home/viewtv/viewtv-backups/acceso-ubuntu-regla-20261120-135617.tar.gz`

SHA-256:
`49e28afadf3440172dc3e72f2477f54c843f4260b79f62499cb5e6b1ded3e42a`

Se verificó `tar -tzf`: contiene solamente `docs/ENTORNO-CONECTOR.md`.
`AGENTS.md` es un archivo nuevo, por lo que no tenía versión anterior
que respaldar.

## Pruebas concretas ejecutadas

| Capacidad | Evidencia obtenida | Conclusión |
|---|---|---|
| Conectividad | list_devices devolvió LAPTOP-V2QSMC01 Online, agente 0.3.4 | Funciona |
| PowerShell nativo Windows | Get-Location y Get-Item C:\Users\Public devolvieron propiedades | Funciona |
| WSL Ubuntu | wsl.exe --exec /bin/bash -lc 'pwd; whoami; ls -ld ~' devolvió usuario viewtv | Funciona |
| Comandos WSL | git status, git log --oneline -20, docker ps, docker compose ps, df -h | Funciona |
| Alembic | docker exec -w /opt/viewtv/backend viewtv-worker-1 python -m alembic current | 0012_inicio_torrent |
| Lectura de Windows | read_file C:\VIEWTV\viewtv_modo_cine.py (solo primeras 10 líneas) | Funciona |
| Lectura directa de WSL vía UNC | read_file \\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\docs\ORGANIZADOR-QUIESCENCIA-NTFS-SANDBOX.md | Funciona |
| Escritura texto en WSL vía UNC | write_file scripts/viewtv_windows_broker_handoff_sandbox.ps1, seguido de ejecución real desde PowerShell | Funciona |
| Edición de texto | edit_block aplicó dos cambios localizados a scripts/viewtv_windows_publish_sandbox.ps1 | Funciona |
| Recuperar texto del equipo | read_file y read_multiple_files recuperaron archivos íntegros en la conversación | Funciona |
| Subir/bajar ficheros binarios completos | No se identificó acción dedicada de transferencia binaria en el conector | NO verificado; no afirmar funcionamiento |
| Comandos de administración | El usuario quitó net, sc y runas de blockedCommands; el resto continúa protegido | Cambio comprobado el 20-11-2026 |
| Cuentas Windows separadas | New-LocalUser, LogonUserW, WindowsIdentity.Impersonate y Remove-LocalUser en prueba GUID | Dos SIDs reales y siete comprobaciones correctas; cero cuentas residuales |
| Servicio Windows del broker | No se ha creado ni ejecutado un servicio persistente | Pendiente; tener administrador no demuestra identidad aislada de servicio |
| Escritura sobre archivos de producción | No ensayada | Prohibida en esta fase |

La lectura WSL desde la ruta UNC se probó sin copiar archivos. La escritura de
texto y la edición se ensayaron solamente en el árbol de desarrollo autorizado,
después de un respaldo de los archivos existentes que podrían modificarse.
Que se pueda leer un archivo no demuestra transferencia de bytes arbitrarios
ni elevación de privilegios. El usuario retiró solo net, sc y runas de la lista
blockedCommands. No se han retirado otras protecciones desde el conector.
El ensayo real con dos SID se detalla en
[ORGANIZADOR-SID-SEPARADOS-WINDOWS-SANDBOX.md](ORGANIZADOR-SID-SEPARADOS-WINDOWS-SANDBOX.md).
Hubo un primer ensayo fallido por conservar ACE de lectura de la copia
tras mover una carpeta; se corrigió retirando esa ACE antes del movimiento.

## Situación de los árboles locales

- Árbol principal: /home/viewtv/projects/viewtv, rama inventario-trabajo-local,
  con .bak y archivos sin seguimiento preexistentes: NO TOCAR.
- Árbol aislado: /home/viewtv/projects/viewtv-broker-0013-20261119, rama
  viewtv-seguimiento-descargas-0012, HEAD inicial c473b43, limpio al comenzar.
- Windows: la carpeta C:\VIEWTV\media está fuera del alcance del trabajo de
  desarrollo y no ha sido inspeccionada ni modificada como contenido.

## Incidencia real detectada en producción durante la fase 0

- docker ps: viewtv-api-1 reiniciando (255) usando imagen viewtv:local.
- docker ps: viewtv-worker-1 activo usando imagen viewtv:predeploy-0012-release.
- docker compose ps confirmó el mismo desajuste.
- docker logs de API: "Can't locate revision identified by '0012_inicio_torrent'".
- docker exec -w /opt/viewtv/backend viewtv-worker-1 python -m alembic current:
  0012_inicio_torrent (head).
- docker exec viewtv-worker-1 printenv VIEWTV_ENABLE_DOWNLOAD_START: false.

La causa exacta del uso de viewtv:local en API no se ha establecido. No se
recrearon contenedores, no se migró la base y no se consultó qBittorrent real.
Es obligatorio resolver la incompatibilidad de imágenes y esquema de API y
worker antes de considerar la integración productiva de 0013.

## Disciplina operativa

La ejecución de herramientas ocurre en Windows PowerShell con acceso a WSL.
Para evitar problemas de comillas entre shells, se emplearon comandos directos
como wsl.exe --exec tar y wsl.exe --exec sha256sum.
El conector no sustituye respaldos verificables ni garantiza permisos de
servicio independientes. Si una operación devuelve error, conservar la salida
y no repetir operaciones con efectos desconocidos sin comprobar estado.
