# VIEWTV 0013 — gate ACL obligatorio del SID copiador (solo SANDBOX)

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.
**Prototipo de laboratorio, no apto para producción**. No instala servicio,
no consulta torrents reales, no toca `C:\VIEWTV\media` ni SQLite real.

## Contexto y resultado

La prueba anterior con dos cuentas Windows distintas mostró que
`Directory.Move` **conserva las ACL explícitas** de la carpeta movida y
sus archivos: si el SID de copia conserva lectura, puede acceder al
contenido dentro de la carpeta privada mediante su ruta conocida.
La protección del directorio padre no basta.

Para impedir que el publicador de prueba omita esa condición, se añadió
`scripts/viewtv_windows_copy_acl_gate_sandbox.ps1` y se integró en
`scripts/viewtv_windows_broker_handoff_sandbox.ps1`.

Al utilizar `-BrokerHandoff`, el publicador exige ahora `-CopySid`:
```powershell
& $publisher -SandboxRoot $sandbox -StageName '.viewtv-stage-1' `
  -FinalName 'Prueba' -ApprovalName '.viewtv-approval-1.json' `
  -KeyPath $key -BrokerHandoff -CopySid $sidCopiador
```
Estas variables son **solo ilustrativas**; el ejemplo no concede
permisos ni autoriza un uso fuera del sandbox GUID marcado.

La validación de ACL es exclusivamente de lectura y falla con excepción
sin iniciar movimiento si encuentra:
- SID de copia ausente, mal formado, igual a la identidad de broker
  o a la identidad que está ejecutando el publicador.
- ACL heredadas o no protegidas, propietario distinto de
  BUILTIN\Administradores, ACE denegadas o ACE inesperadas.
- ACE del SID copiador en staging o en **cualquier archivo**, incluso
  una ACE con acceso de solo lectura; ACE amplias como BUILTIN\Users.
- ACL o entradas inesperadas en la raíz, carpeta privada, escrow o destino.
- Derechos del `RestrictedCodeSid` superiores a lectura.
- Enlaces de reanálisis, archivos vacíos, tamaño mayor de 32 MiB,
  subdirectorios o más de 20 archivos en staging.

Excepción deliberada: la raíz GUID puede conceder al SID copiador
`ReadAndExecute` y `Synchronize`, **sin permiso de escritura**,
para que acceda a sus archivos temporales antes del sellado.
Staging sellado, escrow y destino no admiten ninguna ACE de ese SID.

La comprobación se ejecuta antes del primer `Directory.Move`, después
de la entrega al escrow privado, inmediatamente antes del movimiento final
y sobre el destino publicado. Además se conserva la validación del
manifiesto firmado, hash SHA-256, identidad NTFS y preflight de handles.
Si falla tras el primer movimiento, se deja el escrow para revisión;
**no hay reintento ni reversión automática**.

El modo histórico sin `-BrokerHandoff` permanece sin cambios y **no
promete** esas propiedades. Los argumentos de SID en modo histórico
se rechazan para evitar una falsa sensación de seguridad.

## Pruebas ejecutadas y evidencias

`test_viewtv_windows_broker_handoff_sandbox.ps1`: **9 comprobaciones
correctas**. Se incluyen rechazos de ausencia de SID, ACE de lectura
del SID señalado, ACE del grupo Users, vault desprotegida, escritor
abierto y manifest alterado. La prueba de este módulo utiliza un SID
sintético para aislar el comportamiento del gate; **por sí sola no
demuestra que esa cuenta exista**.

`test_viewtv_windows_distinct_sids_sandbox.ps1`: **12 comprobaciones
correctas**, con dos cuentas locales temporales reales, diferentes y
no administrativas. Valida rechazo antes del sellado, rechazo de una
ACE de lectura inyectada del SID real, aceptación después de revocar
todas las ACE de copia, inspección de escrow y del resultado, rechazo
de escritura bajo ambas identidades y bloqueo de un escritor preabierto.
El test invoca el guard de ACL con SID real y ejecuta los movimientos
por impersonación de broker; **todavía no arranca el publicador
firmado bajo una cuenta de servicio real**.

Regresiones sin cambios:
- Publicador existente: **20 comprobaciones correctas**.
- Token restringido / quiescencia: **29 correctas**.
- Backend WSL: **545 passed, 2 warnings** conocidos, exit code 0,
  ejecución sin caché y sin escribir bytecode.
- Parser PowerShell 5.1 de los archivos nuevos y editados: correcto.
- `git diff --check`: correcto.

### Incidencia de ensayo, resuelta sin tocar producción

El primer test integrado protegió la raíz GUID **después** de escribir
su marcador, usando ACE de directorio que no se heredaban. Esto dejó
el marcador ficticio sin ACL de lectura y bloqueó la verificación y
la limpieza del test. La causa se comprobó con `Get-Acl`, y la prueba
se corrigió para crear primero una raíz protegida con ACE heredables
y escribir el marcador después.

El GUID fallido
`C:\Users\Public\viewtv-win-sandbox-3024d0bc7fc244bea8f77c15d90d3fef`
se inspeccionó individualmente: solo contenía el marcador de 31 bytes,
su aprobación de prueba, una carpeta escrow vacía y un staging con
`ficticio.mkv` sintético de 9216 bytes. Se comprobó la ausencia de
reparse points, nombre GUID y parent `C:\Users\Public`, y fue
eliminado con `Directory.Delete` sobre **esa ruta exacta**.
No se tocaron carpetas ajenas ni librerías reales.

Estado final: cero cuentas Windows temporales y cero directorios
`viewtv-win-sandbox-*` pendientes de este ensayo.

## Respaldos verificados

Antes de editar los seis archivos existentes:
`~/viewtv-backups/gate-acl-sid-publisher-pre-20261120-142606.tar.gz`

SHA-256:
`68bb92973d7aa73f6a9e5e72ae9a5d97fb416bf1ea6dc5ab4084e7d1f24b425a`

`tar -tzf` confirmó:
- `scripts/viewtv_windows_broker_handoff_sandbox.ps1`
- `scripts/viewtv_windows_publish_sandbox.ps1`
- `scripts/test_viewtv_windows_broker_handoff_sandbox.ps1`
- `scripts/test_viewtv_windows_distinct_sids_sandbox.ps1`
- `docs/ORGANIZADOR-ENTREGA-PRIVADA-NTFS-SANDBOX.md`
- `docs/ORGANIZADOR-SID-SEPARADOS-WINDOWS-SANDBOX.md`

La versión del test fallido del marcador y el guard nuevo también
quedaron preservados en
`~/viewtv-backups/gate-acl-test-fallo-marcador-20261120-143122.tar.gz`,
SHA-256
`368c691c0cfdc13da8e3f5cf32603838b43d7b4c65819adc19498a866bde8a92`;
`tar -tzf` mostró exactamente ambos scripts. El guard y este
documento son archivos nuevos, sin versión anterior que respaldar.

## Límites pendientes y seguridad

- **El SID de copia sigue viniendo del invocador**, no de un registro
  independiente protegido por el broker. Un cliente que suplante ese
  argumento podría sortear el gate. Un broker definitivo debe obtener
  los SID de una configuración protegida administrada fuera del worker,
  y comparar también el token real del proceso.
- La identidad de publicación sigue siendo elevada en el test principal;
  no se ha creado un servicio Windows no administrativo con un secreto
  propio. El control no es una barrera contra el propietario del proceso
  privilegiado, administradores ni un token hostil.
- El preflight histórico de quiescencia aún espera el ACE de lectura
  `RestrictedCodeSid`. La ruta completa de publicación con el broker
  de SID separado no está validada de extremo a extremo como servicio.
- No se ha probado la validación viva de lease, intento y torrent
  desde una autoridad separada, replay global por descarga, caídas
  físicas ni medios de varios GiB. No existe transacción NTFS+SQLite.
- Hay una incidencia productiva **no tocada**: API 0012 reiniciándose
  con imagen diferente de la del worker. No desplegar 0013 mientras
  persista la incompatibilidad.

**Decisión:** gate añadido y probado solo en sandbox; mantener el
PR #2 en borrador, sin merge ni despliegue. La fase 1 continúa abierta.
