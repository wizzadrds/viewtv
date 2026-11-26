# VIEWTV 0019 — Autorización separada del administrador (todavía sin borrados)

Fecha: jueves 26 de noviembre de 2026, Europa/Madrid.
Rama exclusiva: **viewtv-seguimiento-descargas-0012** del repositorio wizzadrds/viewtv.
PR #2: **abierto, en borrador y sin fusionar**.
Estado: **prototipo offline con firma**, verificado en datos ficticios; no se ha dado de alta administrador real, no hay credenciales en producción y no existe autorización efectiva para eliminar películas.

## Contexto y decisión

La biblioteca de películas se comparte entre perfiles, mientras que cada marca «vista» es individual. Marcar vista una película o solicitar su retirada no autoriza a borrar el archivo de otros perfiles. Tampoco el PIN del perfil equivale a la credencial administrativa.

Hitos previos:
- 0015: sección Espacio, vistas por perfil, solicitudes de revisión, cancelación y caché propia protegida.
- 0016: auditoría de hardlinks NTFS de Windows; dos publicaciones verificadas y material sin diario protegido.
- 0017: volumen privado de caché con cuota efectiva solo para futuros escritores propios; backend/frontend sanos.
- 0018: preflight local de solo lectura que cruza SQLite, Jellyfin, diarios Windows, archivos NTFS y qBittorrent. Cuatro películas bloqueadas. Los torrents contienen 6 archivos y los diarios solo incluyen 2, así que 4 adicionales quedan sin permiso de retirada.

## Cambios de código (0019, sin despliegue)

**worker/retirement_authorization_0019.py**
- Introduce una autorización administrativa independiente de autenticación de perfiles, cookies o PINs.
- Antes de proponer una aprobación, exige que el preflight solo presente el motivo «falta_autorizacion_administrador». Un torrent activo, archivos ajenos, perfil que no la ha marcado vista, solicitud ausente, identidad ambigua o cambio de datos bloquean el proceso.
- Genera una huella SHA-256 de TODAS las evidencias: película y descarga exactas, marcas y peticiones, diario y su contenido, Windows NTFS, Jellyfin y archivos/estado qBittorrent. No usa el título para inferir titularidad.
- El desafío contiene ID de película, ID de descarga, huella de la evidencia, nonce aleatorio de 128 bits y caducidad de diez minutos. Debe confirmarse exactamente «RETIRAR MEDIO [id] DESCARGA [id]».
- Firma HMAC-SHA256 con clave de 32 bytes, creada y custodiada por un administrador externo al navegador. La clave nunca proviene de JWT_SECRET y no se genera ni despliega en este hito.
- Lectura de clave solo desde fichero ya provisionado, de propietario único, modo 0600, directorio 0700, sin enlaces ni ubicaciones de Windows o del repositorio.
- Ejemplo de **registro de consumo único** mediante SQLite privada y transacción BEGIN IMMEDIATE; rechaza reuso de nonce y es seguro ante múltiples intentos concurrentes en el sandbox.
- El registro devuelve explícitamente autoriza_borrado_fisico=false. Validar la firma NO activa ninguna operación sobre archivos, qBit ni Jellyfin.

**scripts/viewtv_retirada_admin_preflight_0019.py**
- Combinación read-only del preflight 0018 con las condiciones para plantear autorización administrativa, sin emitir ningún ticket de producción, sin credencial y sin cambiar archivos.
- Repite auditoría Windows antes y después de consultar SQLite/Jellyfin/qBit y rechaza si hay diferencias. No acepta ID o ruta de película como parámetro externo.

**backend/tests/test_retirada_autorizacion_0019.py**
- Usa claves de ejemplo y SQLite temporal solo dentro de sandbox; no entra en Windows/media, ni usa PINs reales.
- Prueba modificaciones de identidad, huella, firma, secreto, tiempo, operación, nonce y confirmación escrita.
- Verifica rechazo de permisos inseguros, symlinks de clave/diario y consumo repetido, incluso con dieciséis intentos simultáneos.
- Comprueba que si cambia una prueba de qBit/Jellyfin/SQLite/diario, no se puede proponer o reutilizar el desafío.

## Resultado real de preflight 0019 (solo lectura)

- Películas inspeccionadas: **4**
- Candidatas sin otros bloqueos: **0**
- Películas que carecen de solicitud de retirada pendiente y vista de todos los perfiles: **4**
- Películas sin diario único: **2**
- Películas con torrent activo o incompleto según política de retirada: **2**
- Películas con listado qBit no verificable íntegramente para retirada: **2**
- Clave administrativa configurada en la API: **NO**
- Aprobaciones reales emitidas: **0**
- Autorización para borrar: **NO**
- Archivos o torrents reales modificados: **0**

Los datos se han obtenido sin escritura con el comando local Python del preflight. No se ejecutó un signer contra producción ni se generó ninguna credencial. La firma de laboratorio es un prototipo: no hay integración en Windows ejecutora, alta real del administrador ni bloqueo atómico de Jellyfin/qBittorrent, por lo que no autoriza borrados.

## Seguridad y continuidad

Respaldo previo de código y documentación verificado:
**/home/viewtv/viewtv-backups/retirada-autorizacion-pre-20261126-202923.tar.gz**
SHA-256: **97a89dcb7e445f4023a6728606387c312b947742bafccda737ae97bbbf74fb96**.
Inspección tar -tzf correcta. No contiene .env, claves, bases de datos, diarios de publicación ni multimedia.

**Pruebas específicas de retirada y firma administrativa: 94/94 PASS. Suite backend completa: 1148/1148 PASS**, con dos advertencias de deprecación de dependencias externas. Ejecutada en contenedor de pruebas sin red. **Ruff PASS** para el módulo de autorización, pruebas y script de preflight. Smoke real de solo lectura **10/10 PASS**. No requiere migración de la base de producción ni cambios en los contenedores. La versión desplegada continúa siendo API/frontend **0017**, worker **0015**. PR #2 permanece OPEN/DRAFT.

## Pendientes imprescindibles (antes de la app Samsung)

1. Dar de alta una credencial real de administrador en el host protegido, con proceso de firma, auditoría, revocación y controles antiabuso; **no compartirla con frontend o PINs**.
2. Resolver los **cuatro archivos de qBit no incluidos en los dos manifiestos publicados**, y comprobar si los torrents siguen activos. No borrar originales incompletos, sembrando o compartidos.
3. Crear **exclusión mutua y preflight de última milésima** entre publicador Windows, qBit, Jellyfin y base de datos; impedir carreras o lecturas mientras se opera.
4. Implementar ejecutor Windows por una sola película/descarga bajo autorización concreta, con journal durable y recuperación probada ante fallo parcial real, no solo simulación.
5. Medir espacio de volumen realmente recuperado y distinguir bytes lógicos de hardlinks; probar todo en sandbox antes de tocar películas reales.
6. Integrar solo productores propios de temporales en la caché privada 0017, sin borrar caché de Jellyfin u originales de torrent.

**Orden preservado: gestión real y segura de espacio → app Samsung Tizen profesional → VIEWTV Momentos.**
