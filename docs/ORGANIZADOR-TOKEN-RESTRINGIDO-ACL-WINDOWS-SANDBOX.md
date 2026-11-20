# VIEWTV 0013 — Prueba efectiva de ACL con token Windows restringido

**Fecha:** 20-11-2026. **Solo sandbox. No es separación real de cuentas ni broker de producción.**

## Problema y decisión

La arquitectura 0013 exige que el proceso que copia pueda escribir en
staging sin poder leer la clave del broker, alterar su diario, crear
destinos, modificar ACL privilegiadas o abrir su tubería. Las ACL
anteriores se inspeccionaban desde el usuario Windows que ejecutaba
las pruebas; **no demostraban una denegación efectiva bajo un contexto
con menos permisos**.

En este bloque no se crean cuentas, claves de usuario, servicios,
tareas programadas ni cambios de DACL sobre directorios existentes.
El contexto restringido se obtiene **en memoria**, con
`CreateRestrictedToken` (grupo de Administradores deshabilitado y
privilegios reducidos), una restricción adicional mediante el SID
`RestrictedCodeSid`, `DuplicateTokenEx` y
`WindowsIdentity.Impersonate`. Se verifica que el contexto obtenido
**no sigue siendo administrador**.

**Muy importante:** este token conserva el mismo SID de usuario que
la sesión original. No es un segundo usuario o servicio Windows; una
aplicación maliciosa que pudiera continuar usando el token original
podría eludir la prueba. Lo correcto para producción sigue siendo
dos identidades independientes y una cuenta de broker de mínimo
privilegio, no el token de ensayo.

## Recursos y frontera de ACL ensayados

El ensayo
`scripts/test_viewtv_windows_restricted_acl_sandbox.ps1` crea una
única carpeta aleatoria y marcada
`C:\Users\Public\viewtv-win-sandbox-<GUID>` y conserva todas
las operaciones dentro de ella:

- Raíz: ACL protegida; el contexto completo posee derechos de
  mantenimiento y el token de copia solamente lectura/travesía.
- Staging `.viewtv-stage-1`: inicialmente el token restringido puede
  crear y leer un vídeo ficticio.
- `broker-private`: clave **ficticia**, diario y directorio que el
  token de copia no puede leer ni modificar. El ensayo jamás utiliza
  claves, registros o datos reales.
- Propiedad Windows: la cuenta de ensayo elevada establece
  **Administradores como propietario** de raíz, staging, claves y
  diario, dentro de esta carpeta nueva. El contexto restringido
  deshabilita su pertenencia al grupo Administradores, de modo que
  no obtiene `WRITE_DAC` automáticamente por ser propietario. Tras
  la copia se establece ese propietario también en el vídeo.
- Sellado de ensayo: la cuenta que administra el sandbox cambia
  las ACL de **carpeta y fichero** para retirar escritura al SID
  restringido y permitir lectura. Se comprueba la denegación de
  reapertura para escribir, de creación de subtítulos y de
  recuperación de permisos mediante edición de ACL.
- Publicación ficticia: tras cerrar cualquier descriptor de escritura,
  la identidad completa mueve la carpeta mediante
  `[IO.Directory]::Move()` y verifica SHA-256 del vídeo antes y después.
  El token restringido no puede modificar el archivo publicado.
- Tubería: se crea una primera instancia Win32 bajo un nombre GUID
  de prueba con la DACL existente del broker de sandbox. Un
  `CreateFileW` ejecutado bajo el token restringido recibe
  `ERROR_ACCESS_DENIED`; no se limita a inspeccionar reglas en
  una DACL.

El helper `scripts/viewtv_windows_restricted_token_sandbox.ps1`
encapsula únicamente operaciones de acceso con un token restringido;
comprueba raíz GUID, marcador y ruta canónica antes de cada acceso.
El helper nativo no recibe cuentas ni credenciales y sus operaciones
son fijas; no ejecuta comandos enviados por un cliente.

## Hallazgo negativo que bloquea declarar TOCTOU cerrado

Se crea otro staging `.viewtv-stage-2` con vídeo ficticio.
El token de copia abre un descriptor de **escritura antes del sellado**.
La cuenta de broker de prueba cambia DACL y propiedad. Se observa:

- Abrir **una nueva** escritura con el token restringido falla.
- Sin embargo, el **descriptor abierto antes del cambio de ACL
  conserva su permiso para modificar los bytes**, aunque el
  archivo haya sido sellado. Se demuestra una alteración efectiva del
  SHA-256 tras cerrar el descriptor.
- Mientras ese descriptor permanece abierto, en este NTFS
  `Directory.Move` rechaza el traslado.

**Conclusión:** retirar permisos mediante DACL protege contra **nuevas
aperturas** de escritura, pero no revoca los descriptores previos.
No se ha probado ni implementado un protocolo que garantice que
Docker y el proceso de copia hayan liberado todos sus handles.
El broker definitivo debe bloquear publicación hasta poder
comprobar quiescencia, recuperar un estado seguro tras bloqueo,
volver a verificar manifiesto/identidades y confirmar el lease.
Aun con las pruebas positivas de ACL, **TOCTOU no está resuelto**.

## Reproducción de pruebas

**PowerShell nativo Windows** (no ejecutar como servicio):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_restricted_acl_sandbox.ps1"
```

El script verifica **21 resultados**: estado del token, lectura/escritura
permitida en staging, denegación de clave y diario, denegación del
destino, cuatro controles de cambio de ACL, sellado de vídeo y
subtítulos, publicación por contexto completo, denegación tras mover,
denegación de tubería y pruebas de handle abierto antes del sellado.
Limpia solamente la carpeta GUID que ha creado y marcado, y rechaza
limpiar si aparecen enlaces de reanálisis en su interior.

Las pruebas no leen qBittorrent, SQLite de producción ni torrents.
No hay cambios en `worker/main.py` ni en el canal del broker.
No hay un servicio real bajo un SID diferente, ni un cambio de ACL en
`C:\VIEWTV\media` o rutas persistentes.

## Siguientes requisitos

1. Acordar cómo se crearán y gestionarán **dos identidades Windows
   verdaderamente independientes**, con secretos no compartidos,
   privilegios mínimos, control de grupos, herencia, propietario y
   pruebas de `AccessDenied` desde la cuenta de copia real.
2. Ensayar de forma aislada un broker iniciado bajo la identidad
   dedicada, un cliente con identidad distinta, y protección de
   claves/diario/pipe/destino sin usar el token original privilegiado.
3. Diseñar la entrega de control del staging: cierre verificable de
   handles, autoridad sobre ACL/propiedad y revalidación contra
   mutaciones y reemplazos.
4. Conectar autoridad independiente de lease/attempt/qBittorrent y
   manifiesto al broker; probar caída/replay, varios GiB y
   `0012→0013→0012` en copia fresca antes de cualquier despliegue.

**Producción sigue VIEWTV 0012;
`VIEWTV_ENABLE_DOWNLOAD_START=false`. PR #2 permanece en borrador y
sin fusionar.**

## Resultado final verificado en el equipo

- **21 comprobaciones** con el token restringido: todas correctas,
  incluidas denegaciones de acceso efectivas al pipe Win32, diario, clave,
  destino y cambios de DACL, además del fallo deliberadamente
  reproducido de **descriptor preabierto aún escribible**.
- Regresión anterior de ACL Windows: correcta.
- **5** comprobaciones Win32 de primera instancia: correctas.
- **24** comprobaciones del canal autenticado: correctas.
- **8** pruebas de timeouts: correctas.
- **20** escenarios del publicador Windows y **11** del diario: correctos.
- **12** pruebas del puente Windows→WSL: correctas.
- Suite backend: **545 pruebas aprobadas**, dos avisos de deprecación
  ya conocidos. Ningún archivo backend ha cambiado en este bloque.
- `git diff --check`: correcto. Ningún directorio GUID o clave de
  prueba quedó en `C:\Users\Public`, `%TEMP%` ni `/tmp`.
- El directorio Git original `inventario-trabajo-local` sigue intacto;
  se usan exclusivamente los archivos nuevos del ensayo y este documento
  más la actualización del contrato de broker.

**Advertencia de interpretación:** el contexto restringido no puede
recuperar su rol de administrador ni editar las ACL de los objetos de
prueba cuyo propietario es Administradores, pero un proceso no confiable
ejecutado bajo el **token original** todavía podría hacerlo. Esta prueba
no certifica separación de confianza frente a software malicioso que
tenga acceso a la sesión Windows sin restringir.
