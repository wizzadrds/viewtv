# VIEWTV — Contrato de broker Windows y confinamiento ACL (diseño 0013)

**Estado:** diseño de seguridad y ensayo ACL solamente. **NO ES UN BROKER IMPLEMENTADO NI APTO PARA PRODUCCIÓN.**
Fecha: 19-11-2026. Rama de revisión: `viewtv-seguimiento-descargas-0012`.

## Evidencia de partida

- Producción usa 0012, verificación activa e inicio automático desactivado. No modificar `C:\VIEWTV\media`, qBittorrent ni la base real.
- Cola 0013 (solo desarrollo): leases de 180 s, renovación propia hasta 900 s y hasta tres intentos; una confirmación antigua o caducada se rechaza.
- En NTFS/DrvFS `renameat2(RENAME_NOREPLACE)` de directorios falla con `EINVAL`. Para **carpetas nuevas** está probado `[System.IO.Directory]::Move()` invocado desde PowerShell **nativo Windows** y sobre el mismo volumen, no desde WSL.
- El HMAC del prototipo vincula sandbox, staging, destino, nonce, caducidad y SHA-256 por archivo; en las pruebas el firmante y el publicador comparten **el mismo usuario Windows**. Eso no separa privilegios, no previene replay durable y no constituye autenticación de producción.
- La sesión usada para esta inspección **no es administradora**: no se han creado usuarios, servicios, cuentas gestionadas ni nuevas ACL sobre rutas existentes.

## Fronteras de confianza propuestas

1. **Docker/worker no es autoridad para publicar**: entrega una intención no confiable con `version`, `job_id`, `download_id`, `attempt_id`, `nonce`, `expires_utc`, identificador **opaco** de staging, `target_kind` y manifiesto ordenado de nombres relativos, tamaños y hashes SHA-256. No se admiten rutas absolutas ni comandos del cliente.
2. **Servicio de autorización independiente del worker**: debe consultar SQLite 0013, la propiedad y vigencia de lease, completado/verificación y la identidad qBittorrent por lecturas GET. Debe emitir una decisión acotada para **una única intención**. No alojar su secreto de firma ni credenciales elevadas en el contenedor de copia.
3. **Broker Windows, con identidad distinta y reducida**: recibe solicitudes a través de un canal local autenticado cuyo acceso esté limitado por ACL; no ejecuta texto, scripts, ni rutas proporcionadas por Docker. Traduce identificadores a raíces configuradas por el administrador. Valida el estado autorizado inmediatamente antes de publicar.
4. **Separar ACL**: la identidad de copia solo escribe en staging; la identidad del broker controla la raíz de publicación y su diario de intenciones; la identidad Jellyfin lee el destino. Las claves/diario del broker no están montados en Docker. Impedir escritura para `Everyone`, `Users` o `Authenticated Users` en las raíces protegidas.
5. **El propio broker mantiene una lista de raíces permitidas**; para la fase actual es únicamente un sandbox nuevo, marcado y generado bajo `C:\Users\Public\viewtv-win-sandbox-<GUID>`. `C:\VIEWTV\media` y cualquier volumen de medios real quedan explícitamente fuera del alcance. No aceptar enlaces de reanálisis, ADS, rutas UNC, nombres reservados, escapes relativos, ni diferencias engañosas de mayúsculas.

## Contrato de publicación propuesto (NO IMPLEMENTADO)

- Petición `prepare`: versión, identificadores estables, nonce aleatorio, vencimiento corto, identificadores de volumen y carpeta, manifest de vídeo + subtítulos y huella del plan. El broker **no confía en la firma creada por el worker**; obtiene una autorización de una autoridad independiente y verifica el resultado.
- Respuesta `prepared`: identificador de operación, manifest aprobado, estado de lease y vínculo al mismo trabajo. Aceptar esta respuesta **no significa publicación**.
- Prepublicación: comprobar autorización vigente, lease, verificación de torrent y archivos, ACL y espacio libre; mantener posesión/exclusión efectiva del staging y revalidar su identidad y bytes para reducir TOCTOU. Si no hay forma de inmovilizar el staging frente a mutaciones, **no publicar**.
- Antes de `Directory.Move`: persistir en un diario de acceso restringido `publishing` con `attempt_id`, nonce y hash del manifiesto; forzar sincronización de los datos críticos. Publicar solo carpeta nueva, mismo NTFS, sin reemplazo.
- Después del movimiento: releer y verificar destino y registrar `published_verified` de manera durable; solo entonces el orquestador puede intentar `confirm_organization` con un lease todavía vigente. Nunca concluir éxito por HTTP 200 ni por una respuesta perdida.
- Resultado ambiguo, timeout, crash, colisión, ACL denegada, lease perdido o discrepancia de hashes: **no reintentar el movimiento**. Conciliar journal + staging + destino + base de datos; cualquier contradicción es `requiere_revision`. Si hay destino verificado y lease vencido, registrar hallazgo pero no confirmar mediante un worker antiguo.
- Replay: operación `attempt_id` y nonce únicos, reserva durable; el mismo nonce repetido **nunca genera una segunda publicación**. La expiración permite únicamente inspección de solo lectura, no una publicación nueva.
- Heartbeat: independiente de callbacks de copia, mediante una tarea concurrente que renueva el lease; detiene la autorización si se pierde o si el I/O queda bloqueado demasiado tiempo. No hay transacción atómica única entre SQLite y NTFS: la conciliación durable es imprescindible.
- Respuesta externa solo con estados y errores predefinidos, nunca rutas reales, hashes del torrent, PIN, claves ni trazas internas.

## Criterios para habilitar pruebas de integración posteriores

1. Crear y comprobar **identidades realmente separadas** sin conceder privilegios administrativos al worker o a Docker; confirmar sus ACL con pruebas de acceso denegado **desde la identidad de copia**.
2. Elegir y probar un canal Windows→servicio de autorización con autenticación mutua y control de replay. Dado que PowerShell→WSL/Docker funcionó y WSL→PowerShell falló en este equipo, preferir broker Windows iniciador; no asumir conectividad inversa.
3. Aislar un diario durable, demostrar replay y recuperación tras corte **antes/después** de `Directory.Move`; verificar que no hay grupos de archivos expuestos parcialmente ni sobrescrituras.
4. Probar con archivos ficticios de tamaño real, copia larga, lease perdido, colisión simultánea, antivirus, permisos denegados, destino preexistente y revalidación TOCTOU.
5. Solo posteriormente evaluar una migración de **copia fresca** `0012→0013→0012`, con integridad, claves foráneas y cuentas conservadas. Sin despliegue ni conexión a `worker/main.py`.

## Ensayo ACL de este entregable

`scripts/test_viewtv_windows_acl_sandbox.ps1` solo crea un sandbox aleatorio bajo `C:\Users\Public`, protege su ACL (sin herencia, acceso explícito del usuario de prueba, SYSTEM y Administradores), valida la protección y publica un vídeo y un subtítulo ficticios mediante el publicador existente. Destruye **solo su propio sandbox y clave de prueba recién creados**. No crea identidades ni cambia permisos de carpetas previas.

**Límite de evidencia:** ejecutar como el mismo usuario no demuestra denegación para una identidad Docker independiente. El control de ACL es una prueba preparatoria, **no una certificación de confinamiento de producción**.

## Resultado del ensayo ejecutado en Windows

- PowerShell 5.1, sesión no administradora; prueba ejecutada sobre **una carpeta recién creada** con nombre GUID en `C:\Users\Public`.
- ACL protegida, sin herencia y con exactamente **tres entradas explícitas**: usuario que ejecuta la prueba, SYSTEM y Administradores. No se crearon cuentas ni se alteraron ACL de carpetas existentes.
- Publicación nativa de **una carpeta con un vídeo y un subtítulo** correcta; ambos hashes SHA-256 coinciden después de la operación y no existe staging duplicado.
- Segunda publicación con denegación temporal `CreateDirectories` en la raíz ficticia: **rechazada antes del movimiento**, staging conservado y destino ausente. La ACL del test se restauró inmediatamente después.
- Para evitar pedir `SeSecurityPrivilege` al ajustar una DACL, la prueba de denegación utiliza `[System.IO.Directory]::SetAccessControl()` con un `DirectorySecurity` construido explícitamente, sin editar SACL. El intento inicial usando `Set-Acl` para esa denegación falló; no se elevó el proceso.
- Se eliminaron únicamente el sandbox y la clave efímera creados por este test; no se tocó `C:\VIEWTV\media`. La prueba **no certifica el aislamiento entre dos usuarios Windows distintos**.

Invocación utilizada (**PowerShell de Windows**, nunca desde WSL):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv\scripts\test_viewtv_windows_acl_sandbox.ps1"
```

**Criterio de cierre de este bloque:** contrato documentado y ACL de sandbox demostrada. **Bloqueo para siguiente fase:** falta una identidad Windows independiente para el broker y ensayos reales de acceso denegado entre cuentas; no declarar el protocolo completo ni habilitar producción.

## Ensayo posterior: canal IPC Windows sin permisos de publicación (20-11-2026)

Se añadió un prototipo de admisión por `NamedPipeServerStream` restringido
a sandbox Windows, con HMAC-SHA-256, mensajes acotados y registro durable
de nonce contra replay. Está documentado y probado en
[ORGANIZADOR-CANAL-BROKER-WINDOWS-SANDBOX.md](ORGANIZADOR-CANAL-BROKER-WINDOWS-SANDBOX.md).
**No es un broker operativo:** continúa utilizando una clave compartida por
el mismo usuario Windows, sin prueba entre cuentas ni autenticación mutua del
servidor, y **no llama al publicador ni verifica la cola 0013**.
No invalida ninguno de los bloqueos de seguridad anteriores.

## Ensayo posterior: token restringido y ACL efectivas (20-11-2026)

Se comprobaron permisos **con un token de impersonación Windows restringido**
bajo un sandbox nuevo en `C:\Users\Public`. Se verificó la denegación de
lectura de clave, lectura/modificación del diario, creación de destino,
alteración de ACL y conexión al pipe del broker. Tras cambiar DACL y
propietario de staging/vídeo bajo la identidad completa, la cuenta de
ensayo restringida dejó de poder abrir **nuevas** escrituras; el broker
ficticio pudo mover la carpeta por NTFS.

**Hallazgo crítico:** un descriptor de escritura abierto **antes**
del sellado siguió modificando el fichero después del cambio de ACL;
`Directory.Move` no pudo ejecutarse mientras el descriptor permanecía
abierto. Por ello **no se declara TOCTOU cerrado**.

El token restringido sigue teniendo **el mismo SID de usuario** que
la cuenta de prueba; no sustituye identidades Windows independientes ni
previene que un proceso que posea el token completo omita la restricción.
Los ensayos y detalles de protección de propietario se documentan en
[ORGANIZADOR-TOKEN-RESTRINGIDO-ACL-WINDOWS-SANDBOX.md](ORGANIZADOR-TOKEN-RESTRINGIDO-ACL-WINDOWS-SANDBOX.md).
No se han creado cuentas ni servicios ni tocado ACL fuera de carpetas GUID
propias de prueba. La sesión usada para este nuevo ensayo sí dispone de
privilegios elevados, a diferencia de la sesión inicial descrita arriba.
