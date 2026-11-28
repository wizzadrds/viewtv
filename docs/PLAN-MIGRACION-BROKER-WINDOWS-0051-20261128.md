# VIEWTV 0051 — plan de migración del broker Windows, sin ejecutar cambios

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`, PR #2 abierta y en borrador, sin fusionar ni desplegar. **Estado observado:** `ESTADO_RETIRADA_0051=BLOQUEADA`. Este documento NO constituye autorización de mantenimiento, alta de servicio ni aprobación de retirar una película.

## Objetivo

Pasar de los ensayos 0037–0050 a una arquitectura donde la identidad y el kernel de Windows, y no solo una transacción SQLite de VIEWTV, impidan a cualquier lector, escritor o cliente qBittorrent interferir durante la retirada de **una película exacta**. El archivo físico solo podría desaparecer después de que **todos los perfiles activos la marquen vista y un administrador independiente apruebe esa película concreta**, con control de lectores, torrents y recuperación duradera.

El hito 0051 no instala ni cambia sistemas: **reutiliza** los auditores Windows 0033, 0037 y 0040, exige **dos observaciones idénticas y verificables por fuente** y transforma las categorías conocidas en un plan de seis fases. El comando `scripts/viewtv_aislamiento_dryrun_0051.py` **siempre sale con código no cero**: 3 para inventario completo pero bloqueo de implantación; 2 si falta o contradice la evidencia. El parser `worker/retirement_migration_plan_0051.py` no recoge ni imprime contraseñas, API keys, IPs, SIDs, hashes de torrents o rutas de medios.

## Hechos actuales confirmados por Windows, solo lectura

- **Identidades:** qBittorrent nativo, Jellyfin nativo y el publicador comparten el SID del operador. La sesión observada está elevada, lo que **no** significa que exista una cuenta broker no interactiva separada. Al menos una de las cuatro ACL de raíz continúa heredada; se requiere aislar todas y verificar permisos **por File ID**, no solo en directorios.
- **qBittorrent:** WebUI configurada y habilitada en el perfil auditado; API key y contraseña cifrada/hasheada presentes **sin revelar sus contenidos**. La instancia nativa tiene listeners no limitados a loopback y reglas de entrada amplias. Ninguna de esas credenciales está acreditada como exclusiva de un broker; una GUI del mismo SID podría enviar START fuera de la bitácora 0046.
- **Jellyfin:** existe listener nativo externo con reglas permisivas. El Docker en puerto local no demuestra que toda la reproducción pase por VIEWTV/HLS v2; la vía nativa debe inventariarse y cerrarse o integrarse bajo admisión y drenaje efectivos.
- **Preflight real previo:** cuatro películas bloqueadas, cero candidatas aptas de autorización, dos torrents fuera de reposo y cuatro archivos auxiliares qBit **protegidos** (488 bytes lógicos, no espacio reclamable). No se autoriza STOP, cambio de prioridades, limpieza ni unlink de ningún contenido.
- **Auditorías 0033 / 0037 / 0040:** seis lecturas sin errores (dos por fuente) y fuentes estables. El gate 0051 también detecta discrepancias entre 0037 y 0040 sobre el SID qBit, en cuyo caso no considera completo el inventario. Que esas lecturas coincidan **no prueba** aislamiento de todas las vías ni una prueba negativa de un usuario malicioso. **Calidad comprobada:** 71/71 pruebas nuevas del planificador PASS; **regresión completa 2.130/2.130 tests backend PASS**, dos advertencias externas Starlette/FastAPI, Docker sin red y fuentes montadas solo lectura; Ruff global `backend worker scripts` PASS; TypeScript PASS; ESLint PASS; smoke HTTP real de solo lectura **10/10 PASS**. Preflight real 0018: 4/4 películas BLOQUEADAS y 2/2 diarios NTFS válidos; qBit 0026: 2 torrents no seguros, 4 extras protegidos (488 bytes lógicos); interlock 0041: 8/8 fuentes coherentes y 6 barreras productivas pendientes. Cero películas borradas, cero torrents modificados.

## Procedimiento propuesto: fases separadas, TODAS sujetas a consentimiento posterior

### Fase 01 — inventario aprobado y paquete de reversión

**Antes de cualquier cambio:** elegir ventana de mantenimiento con el operador, inventariar las aplicaciones legítimas que usan qBit/Jellyfin (Windows, móvil, TV Samsung, Docker, LAN), los torrents no asociados a VIEWTV y sus metadatos protegidos. Identificar qué credenciales y sesiones se tendrían que mover **sin imprimir ni almacenar secretos en Git**. Registrar un plan de reproducción de referencia y los resultados de auditorías 0033/0037/0040/0041.

**Comprobación de salida:** inventario de clientes autorizados, permisos por raíz y volumen, puertos IPv4/IPv6, sesiones existentes, dos torrents y seis archivos; restauración ensayada sobre copia **no productiva** de configuraciones (no trasladar credenciales a ese ensayo). **Reversión:** si falta inventario o acuerdo sobre usuarios legítimos, abortar sin tocar el host.

### Fase 02 — identidad del broker y secretos segregados

**Cambio futuro que requiere autorización expresa:** configurar un **SID de servicio Windows no interactivo diferente** del operador, de qBittorrent, Jellyfin y el publicador. Canal IPC bajo DACL de ese SID, secret-store privado del broker con acceso mínimo; no dar a la GUI ni a VIEWTV capacidades para alterar la credencial de qBit. No activar operaciones destructivas.

**Comprobación de salida:** un cliente permitido entra a la tubería y otro SID distinto falla desde un proceso independiente; validar token del peer con `RunAsClient`, no con texto de petición; verificar anti-replay, cierre y crash; exigir SID/ACL del almacén de clave verificados y **ningún secreto expuesto por logs**. **Reversión:** deshabilitar el servicio nuevo, retirar exclusivamente sus credenciales/entradas recién creadas bajo custodia y restaurar la configuración respaldada, sin detener torrents ni tocar originales.

### Fase 03 — control exclusivo de START/STOP del torrent exacto

**Cambio futuro que requiere autorización expresa:** inventariar WebUI/GUI y cualquier API client; migrar de forma controlada el acceso de escritura al broker, sin romper la lectura/descarga legítima ni torrents ajenos. Aplicar cortafuegos/escucha/credenciales **solo después de verificar qué clientes perderían acceso**. Mantener la bitácora START durable antes del POST y el registro de STOP por hash, **nunca reintentar POST ambiguo de forma automática**.

**Comprobación de salida:** GUI de operador, WebUI alternativa, reinicio automático, API y LAN **no pueden reanudar el hash custodiado**; un hash ajeno sigue funcionando; extras y metadatos no se eliminan. Test de caída justo antes y después del POST en broker segregado. **Reversión:** restaurar únicamente reglas/configuración del servicio afectado a través de la ventana aprobada, validando que no se han alterado los torrents ajenos; una reversión fallida mantiene toda retirada bloqueada.

### Fase 04 — DACL NTFS y prueba negativa de tercer hardlink

**Cambio futuro que requiere autorización expresa:** aplicar permisos por identidad sobre los dos hardlinks del **mismo volumen + File ID NTFS**, sin eliminar enlaces ajenos ni transferir todo el volumen al broker. No asumir que `DELETE|FILE_SHARE_DELETE` impide `CreateHardLinkW`: el ensayo 0034 demostró que no.

**Comprobación de salida:** desde cada SID lector, Jellyfin/qBit/publicador y otro proceso con una credencial distinta, probar de forma no destructiva apertura, escritura, creación de tercer hardlink, acceso por alias/reparse y handles preabiertos; cualquier vía restante bloquea la operación. El broker debe verificar que existen **exactamente los dos enlaces enumerados y ningún otro**, con mismo File ID/bytes/hash, justo antes de una retirada autorizada. **Reversión:** restaurar los permisos originales **del File ID exacto** desde su copia segura; no borrar ni renombrar películas, no hacer ACL recursivas.

### Fase 05 — Jellyfin/HLS v2 y drenaje efectivo de reproducción

**Cambio futuro que requiere autorización expresa:** hacer pasar las solicitudes autorizadas por la admisión HLS v2 y cerrar o acotar realmente las rutas nativas/Docker, IPv4/IPv6, proxy, sesiones antiguas y aplicaciones de TV. No bastan contadores de sesiones ni `HTTP 200` de salud.

**Comprobación de salida:** un stream abierto previamente, una descarga lenta, acceso directo a Jellyfin y un enlace HLS v1 no pueden atravesar el cierre; todos los perfiles legítimos conservan reproducción normal fuera de una retirada. **Reversión:** restaurar rutas de reproducción originales sin alterar bibliotecas, cachés ni derechos de archivos; cualquier sesión que pueda permanecer abierta mantiene la retirada BLOQUEADA.

### Fase 06 — ensayo de recuperación, aprobación por película y espacio realmente liberado

**No habilitar hasta superar todas las fases anteriores.** Ensayar en un volumen aislado el protocolo de aprobación HMAC de película/descarga/nonce y File ID exacto; la misma autoridad durable debe confirmar consentimiento específico, custodia qBit y journal NTFS. Revalidar **todos los perfiles vistos**, solicitud de retirada válida, doble evidencia del hash, ausencia de extras, dos enlaces exactos, ningún lector vivo y administrador con clave independiente. Evaluar crash justo después de cada unlink y pérdida eléctrica/reinicio real en volumen de pruebas **sin datos personales**, con verificación posterior de metadatos y espacio.

**Comprobación de salida:** reconciliar los dos nombres sin repetir unlink bajo ambigüedad, no tocar torrent ni archivo no solicitado, y demostrar reclamación de bloques reales (no sumar tamaños lógicos de hardlinks). **Reversión:** fallar cerrado con diario a revisión manual si falta un enlace, una firma, hash, File ID, lector o prueba eléctrica; nunca reconstruir sin prueba o borrar para «completar» un journal. Solo tras aprobación expresa de un medio específico podría considerarse una primera ejecución productiva controlada.

## Estado de cierre

El hito 0051 entrega **código de evaluación, evidencia del host y un plan de migración sin cambios productivos**. No hay infraestructura de broker segregada instalada, no existe exclusión real de todas las GUI/WebUI, ni aislamiento HLS/Jellyfin, ni autorización administrativa de ninguna película apta. Por tanto, aunque el inventario resulte verificable, **`puede_instalar_broker=False`, `puede_desplegar_borrado=False`, `autoriza_borrado_fisico=False`**.

**Para ejecutar una fase de mantenimiento** se necesitará aprobación explícita del operador para la fase, cambios propuestos, impacto en reproducción/descargas y prueba de reversión. Esta aprobación técnica no equivale a la **aprobación separada de un administrador para una película concreta**. No se fusiona ni despliega la PR #2 solo porque pase el diagnóstico.
