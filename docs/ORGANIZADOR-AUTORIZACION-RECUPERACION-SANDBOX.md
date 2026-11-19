# VIEWTV — Autorización de publicación y recuperación de solo lectura (sandbox)

**Fecha:** 19 de noviembre de 2026. **Solo demostración de seguridad; NO DESPLEGADO.**

## Objetivo y alcance

Completar la demostración **Docker prepara → Windows publica** con:
1. Una autorización firmada que identifique exactamente el sandbox,
   el staging, el destino, una marca de caducidad, un identificador
   aleatorio y el SHA-256 y tamaño de **cada archivo**.
2. Una inspección de **solo lectura** cuando la respuesta de Windows
   sea incierta, sin volver a copiar ni eliminar nada.

Estos scripts NO trabajan en `C:\VIEWTV\media`, no se invocan desde
`worker/main.py` ni consultan o manipulan qBittorrent, SQLite o Jellyfin.
Solo aceptan sandboxes únicos de prueba bajo `C:\Users\Public`.
Siguen limitados a un vídeo ficticio y sus subtítulos, de hasta 32 MiB
por archivo.

## Cómo funciona la autorización de prueba

- `scripts/viewtv_windows_approval_sandbox.ps1` implementa el
  generador y verificador de autorizaciones HMAC-SHA256.
- Windows genera una **clave aleatoria temporal de 256 bits** en una
  carpeta propia `viewtv-test-key-<GUID>` bajo `%TEMP%`, **fuera**
  de los directorios que se montan en Docker.
- Después de preparar staging, un proceso Windows autorizado crea un
  JSON que contiene un plan serializado y su firma HMAC. El plan
  incluye `sandbox`, `stage`, `final`, `nonce`, `expires_utc`,
  nombres de archivos, tamaños y SHA-256. La firma cubre todos
  esos campos.
- `scripts/viewtv_windows_publish_sandbox.ps1` ahora **requiere**
  ruta a la clave temporal y al plan firmado: rechaza firmas
  cambiadas, claves distintas, planes caducados, destinos distintos
  y archivos que cambien después de la aprobación. Comprueba que la
  autorización pertenece al sandbox concreto y al staging esperado.
- Windows comprueba los hashes **antes y después** de
  `Directory.Move`. Si la verificación posterior falla, **no intenta
  deshacer ni repetir automáticamente la operación**.

**Importante:** la firma protege contra alteraciones accidentales y
contra el contenedor que solo tiene acceso al sandbox. En estas
pruebas, el firmante y el publicador se ejecutan con el mismo
usuario Windows; por tanto, **NO se ha demostrado aislamiento
de credenciales, control de acceso o resistencia a un actor hostil
con permisos de ese usuario**. Nunca trasladar esta clave de
prueba ni el esquema de permisos a producción.

## Conciliación tras respuesta ambigua

El nuevo `scripts/viewtv_windows_reconcile_sandbox.ps1` **no
escribe en disco**. Inspecciona la presencia de staging/destino
y verifica el plan firmado y los hashes correspondientes:

| Estado encontrado | Resultado conservador |
|---|---|
| Solo staging, firma válida y sin caducar | `pendiente_de_publicacion`, no inicia nada |
| Solo destino, contenido correcto con firma válida | `publicada_verificada` |
| Staging y destino presentes | `requiere_revision` |
| Ninguno presente | `requiere_revision` |
| Firma o contenido incorrectos | `requiere_revision` |

Las autorizaciones caducadas **solo se admiten para comprobar un
destino ya publicado**: no pueden autorizar una publicación nueva.
El estado `publicada_verificada` es una constatación del disco,
no modifica ni confirma automáticamente la cola SQLite.

## Pruebas realizadas

- **20 escenarios de PowerShell**: nueve controles previos,
  firma falsificada, contenido alterado tras firmar, caducidad,
  destino distinto y clave errónea; seis estados de conciliación
  (publicada, pendiente, ambigua, corrupta, caducada y ausente).
- **Integración de seis comprobaciones Docker → Windows**: staging
  verificado en contenedor sin red, alteración posterior a la firma
  rechazada, publicación multifichero NTFS, conciliación de solo lectura,
  reintento rechazado y fuentes intactas.
- Todos los archivos son ficticios y las carpetas temporales y claves
  temporales se eliminan al terminar cada test.
- La suite backend existente (488 pruebas, dos avisos de dependencias)
  se ejecuta como regresión, independientemente de los tests
  PowerShell. Ruff y `git diff --check` deben permanecer limpios.

## Lo que FALTA antes de producir

1. Un broker Windows limitado a **identidades y ACL realmente separadas**,
   sin dar a Docker ni al usuario web capacidad de firmar permisos.
2. Protocolo local autenticado, control de replay y estado durable
   de intenciones/confirmaciones con IDs y leases vinculados a SQLite
   y al hash y etiqueta del torrent VIEWTV.
3. Evitar carreras TOCTOU entre lectura de hashes y movimiento:
   abrir y controlar identificadores de archivo, comprobar ACL,
   bloquear fuentes modificables cuando sea posible y reconciliar
   de forma conservadora los resultados desconocidos.
4. Garantías de recuperación tras caída de energía, antivirus,
   espacio insuficiente y archivos de tamaño real.
5. Permisos restringidos a directorios **específicamente autorizados**,
   soporte de series existentes, publicación de grupos y subtítulos,
   y pruebas de extremo a extremo con Jellyfin/TV.
6. Backup fresco y ensayo de migración de producción `0012 → 0013`
   con opciones de recuperación comprobadas.

**No poner en producción estos scripts directamente.** VIEWTV real
permanece en versión `0012`, y el arranque automático de torrents
sigue desactivado.

Documentación relacionada:
[publicación Windows](ORGANIZADOR-PUBLICACION-WINDOWS-SANDBOX.md),
[compatibilidad NTFS](ORGANIZADOR-COMPATIBILIDAD-WINDOWS.md),
[cola de organización 0013](ORGANIZADOR-COLA-0013.md).
