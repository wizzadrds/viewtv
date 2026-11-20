# VIEWTV 0013 — Preflight de quiescencia NTFS en sandbox

**Fecha:** 20-11-2026. **SOLO ENSAYO. No usar en producción ni considerar que el TOCTOU está cerrado.**

## Objetivo

El ensayo anterior con token Windows restringido demostró que cambiar las
ACL de un staging no revoca los descriptores de escritura obtenidos antes
del sellado. Un proceso de copia podría conservar uno de esos descriptores,
aunque el broker impida nuevas aperturas. En el NTFS de este equipo,
`Directory.Move` falla si todavía hay un descriptor incompatible.

Este bloque añade una **comprobación conservadora y de solo lectura**
para detectar algunos descriptores existentes antes de evaluar una
publicación. **No mueve nada y nunca autoriza publicar por sí sola.**

## Componente

`scripts/viewtv_windows_quiescence_sandbox.ps1` proporciona
`Test-ViewtvSandboxQuiescence -SandboxRoot <GUID> -StageName .viewtv-stage-N`.
La llamada se limita a una carpeta marcada
`C:\Users\Public\viewtv-win-sandbox-<GUID>`, rechaza rutas
redirigidas y usa el fingerprint NTFS ya existente para verificar
identidad, enlaces duros y ausencia de entradas inesperadas.

El preflight exige:

1. Staging directo, con nombre numérico controlado, y entre 1 y 20
   archivos regulares directos, de tamaño positivo y hasta 32 MiB
   por archivo; sin subcarpetas ni reparse points.
2. DACL **protegida**, propietario `BUILTIN\Administrators`,
   y ACE de `RestrictedCodeSid` que concede solamente
   `ReadAndExecute` (incluido el posible bit `Synchronize`).
   El mismo requisito rige para la carpeta y cada archivo.
3. Un intento breve de abrir **carpeta y cada archivo sin compartir
   accesos** mediante Win32 `CreateFileW` con `GENERIC_READ`,
   `dwShareMode=0`, `OPEN_EXISTING` y, para carpetas,
   `FILE_FLAG_BACKUP_SEMANTICS`. Se usa también
   `FILE_FLAG_OPEN_REPARSE_POINT`.
4. Fingerprint NTFS estable antes y después del sondeo.

Un fallo de identidad, permisos, acceso exclusivo, entrada no
autorizada o excepción devuelve `requiere_revision` o rechaza la
ruta antes de la comprobación. El resultado positivo se denomina
deliberadamente **`sin_handles_detectados`**, no
`autorizado_para_publicar`.

### Hallazgo corregido durante las pruebas

La primera versión del sondeo utilizaba solo
`FILE_READ_ATTRIBUTES` con compartición cero: **Win32 permitió
abrir el fichero mientras otro descriptor de escritura seguía vivo**.
La prueba negativa lo descubrió, por lo que se descartó esa
implementación. Al usar `GENERIC_READ` y `dwShareMode=0`,
se obtuvo `ERROR_SHARING_VIOLATION (32)` con el escritor antiguo.
Se comprobó tanto el error nativo como el rechazo del preflight.

Este detalle es un resultado específico de esta configuración
Windows/NTFS, no una garantía general sobre todos los controladores
de archivos ni rutas montadas.

## Prueba automatizada

`scripts/test_viewtv_windows_restricted_acl_sandbox.ps1` se amplía
para verificar, además de las ACL y operaciones existentes:

- El staging **no sellado** se rechaza.
- El staging sellado, sin handles, supera el preflight.
- Un escritor con handle abierto **antes** de retirar permisos no
  puede volver a abrir el archivo, pero su handle anterior sigue
  pudiendo modificarlo. El sondeo nativo obtiene error 32 y
  **no permite el preflight**.
- Tras cerrar ese descriptor, el preflight vuelve a reconocer
  la ausencia de handles detectables.
- Un descriptor de **directorio** abierto por el token restringido
  antes del sellado también hace que falle la comprobación,
  aunque el archivo de vídeo ya tenga DACL de lectura.
- Tras cerrar el descriptor de directorio, el preflight vuelve
  a tener éxito. Todas las pruebas se realizan en un sandbox GUID
  nuevo; solo su propia raíz se elimina al finalizar.

El script de pruebas contiene **29 comprobaciones** (las anteriores
de ACL más los nuevos controles de preflight y cierre de handles).

### Reproducción (PowerShell nativo de Windows)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_restricted_acl_sandbox.ps1"
```

## Qué NO demuestra

- **No se ha integrado este preflight con el publicador Windows**
  ni con el broker, los leases o el diario 0013. `worker/main.py`
  permanece intacto.
- Un resultado positivo es una observación **en ese momento**:
  cada descriptor de prueba se cierra antes de que pudiera ejecutarse
  `Directory.Move`. Sigue existiendo una ventana entre el
  preflight y el movimiento; otros accesos o handles de directorio
  podrían abrirse, en particular si un actor conserva el token
  Windows original con permisos administrativos.
- El grupo Administradores y el mismo SID de usuario siguen siendo
  la fuente de autoridad de la prueba. **No existen dos cuentas de
  servicio realmente independientes** y el token restringido puede
  ser omitido por quien controle el proceso original.
- Este mecanismo no bloquea escritores maliciosos que puedan
  restablecer ACL, conseguir duplicados de handles por terceros,
  modificar metadatos, abrir archivos fuera del árbol o actuar
  mediante otro sistema de archivos. No garantiza una transferencia
  atómica de propiedad ni transacciones NTFS/SQLite.
- No se han probado archivos de varios GiB, sesiones Docker/DrvFS
  reales, corte de alimentación, crash ni la migración reversible
  0012→0013 sobre una copia reciente.

## Próximos pasos y condición de seguridad

Para habilitar la publicación hay que ejecutar la copia bajo una
**identidad Windows realmente distinta y sin privilegios**, transferir
la propiedad y el control de staging al broker, verificar que ni
escritores ni descriptores de directorio anteriores puedan alterar
el grupo, revalidar **después** de la copia y justo antes de mover,
y consultar una autoridad independiente de lease/attempt/torrent.
En caso de bloqueo o cambio ambiguo, **requiere revisión**,
no reintento automático.

**Producción sigue en VIEWTV 0012; no se han tocado `C:\VIEWTV\media`,
SQLite real, torrents, Docker Compose, qBittorrent ni Jellyfin.
`VIEWTV_ENABLE_DOWNLOAD_START=false`; PR #2 sigue en borrador.**

## Resultados finales en el equipo (20-11-2026)

- **29 resultados correctos** del test con token Windows restringido,
  incluido el rechazo por `ERROR_SHARING_VIOLATION (32)` de un escritor
  preabierto, el rechazo de un handle de directorio y la aceptación
  posterior tras cerrar ambos; el staging sin sellar se rechaza.
- Prueba ACL Windows anterior: correcta.
- **20 escenarios del publicador Windows** y **11 del diario**:
  correctos y sin cambio funcional de esos módulos.
- **24 escenarios del canal autenticado**, **5 de primera instancia
  Win32**, **8 de timeouts** y **12 del puente Windows→WSL**:
  correctos.
- Suite backend: **545 pruebas aprobadas**, dos advertencias conocidas
  de deprecación. No se modificaron módulos backend.
- `git diff --check` correcto. Comprobación tras las pruebas:
  **0 carpetas GUID, diarios o claves temporales residuales** en las
  raíces permitidas de Windows y WSL.

**Decisión:** mantener el preflight aislado y en modo únicamente
informativo. No unirlo al publicador hasta que las identidades
Windows estén verdaderamente separadas, se controle la entrega de
staging y el broker pueda revalidar lease y contenido antes de mover.
