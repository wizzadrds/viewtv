# VIEWTV 0048 — identidad real del cliente en IPC Windows y anti-replay de laboratorio

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`; PR #2 abierta y en borrador, **sin despliegue ni fusión**. Ámbito: tubería Windows local con GUID y cliente ficticio del propio ensayo, sin conexión con qBittorrent, Jellyfin, archivos multimedia ni cuentas nuevas.

## Problema abordado

El 0047 probó que una DACL de una sola ACE restringe conexiones a una tubería Windows. Sin embargo, una aplicación receptora que aceptara un `SID` declarado dentro de la petición podría confundir **datos suministrados por el cliente con la identidad otorgada por Windows**. La identidad debe comprobarse *del lado del servidor*, mediante la suplantación del token real de quien se ha conectado, antes de interpretar el mensaje.

En 0048 se combina esa comprobación con una gramática mínima de comandos, límite de tamaño y rechazo de identificadores de petición ya usados. El resultado es **solo una demostración en memoria**; no añade todavía un servicio broker, SID propio ni permisos exclusivos sobre qBit/NTFS.

## Implementación y garantía probada

- `scripts/test_viewtv_windows_pipe_peer_protocol_sandbox_0048.ps1`: `NamedPipeServerStream` Win32 con nombre GUID, sin ACL heredadas y una sola ACE Allow para el SID de la sesión **del ensayo**. El cliente conecta con `TokenImpersonationLevel.Impersonation`. Una clase C# compilada localmente mediante `Add-Type` invoca `NamedPipeServerStream.RunAsClient` y `WindowsIdentity.GetCurrent(true)` para recuperar **el SID del token Windows efectivamente suplantado**, sin consultar el texto de la petición. La verificación se realiza antes de aceptar las órdenes.
- La gramática ficticia es `VT48|MOCK_START|<hash de 40 hex>|<nonce de 32 hex>`; no acepta operaciones sin hash, `START all`, hash que no coincide con el objetivo sintético, campo adicional `SID=...`, letras o estructuras no canónicas. Solo un `HashSet` del ensayo recuerda los nonces consumidos durante la **misma vida del proceso**; repetir uno devuelve `DENIED_REPLAY` y no ejecuta nada.
- Se valida igualmente que un llamador con identidad no verificada sea denegado, aunque presente un nonce y hash correctos. El ensayo no pasa credenciales ni hashes reales a Windows; usa un hash sintético y GUID aleatorios y devuelve **solo etiquetas categóricas**, nunca SIDs, hashes ni nonces.
- `worker/retirement_peer_protocol_gate_0048.py` valida de forma estricta las once líneas de prueba, rechazando informes truncados, duplicados, falsos permisos, alteraciones de estados o intentos de filtrar secretos.
- `scripts/viewtv_retirada_peer_protocol_0048.py` realiza dos ejecuciones Windows independientes y devuelve `ESTADO_RETIRADA_0048=BLOQUEADA`; código 3 si los informes coinciden y son válidos, 2 si hay errores. **Nunca código 0 ni permiso de borrado.** No acepta argumentos de ruta, SID ni película.

## Resultados

La prueba Windows directa obtuvo `SID_DEL_CLIENTE_OBTENIDO_POR_WIN32=PASS`, `SID_EN_PAYLOAD_NO_ES_AUTORIDAD=PASS`, `START_ALL_Y_HASH_AJENO_DENEGADOS=PASS`, `NONCE_REUTILIZADO_DENEGADO=PASS`, `SID_NO_VERIFICADO_DENEGADO=PASS` y `SOLO_MOCK_START_SIN_EFECTOS=PASS`. Se declaró expresamente `REPLAY_DURABLE_TRAS_REINICIO_INSTALADO=NO`, `BROKER_SID_DISTINTO_PRODUCTIVO=NO`, `QBIT_REAL_CONTACTADO=NO`, `ARCHIVOS_REALES_ELIMINADOS=0` y `TORRENTS_REALES_MODIFICADOS=0`.

El runner sobre WSL validó **2/2 ejecuciones Windows independientes** y devolvió BLOQUEADA con cuatro barreras. `backend/tests/test_retirement_peer_protocol_gate_0048.py`: **50/50 pruebas PASS**, incluyendo validación de informes falsificados, secretos, caducidad del contrato y retorno bloqueante del runner. Ruff global PASS.

**Regresión completa confirmada:** **1.949/1.949 pruebas backend PASS** en Docker sin red, fuentes en montaje de solo lectura, con dos advertencias externas de Starlette/FastAPI. Ruff global `backend worker scripts` PASS; TypeScript PASS; ESLint PASS; smoke HTTP real de solo lectura **10/10 PASS**. Auditoría Windows directa PASS; runner WSL **2/2 informes válidos** y retorno bloqueante. Preflight real 0018: **4/4 películas bloqueadas**, **2/2 diarios NTFS verificados**, autorización de borrado NO; custodia qBit 0026: **dos torrents sin reposo seguro, seis archivos inventariados, cuatro extras protegidos (488 bytes lógicos)**. Interlock real 0041: **8/8 informes coherentes**, **6 barreras de producción pendientes**, estado BLOQUEADA, 0 archivos eliminados y 0 torrents modificados.

## Límites de seguridad y ruta de cierre

**Esta prueba NO demuestra un broker con SID independiente:** el servidor y el cliente de laboratorio usan el SID del operador y el mismo proceso. Se verifica que Windows reporta la identidad por su token, pero **cualquier proceso con el mismo SID autorizado** puede conectar a esta DACL. Tampoco demuestra rechazo ante un segundo usuario real, ni instala cuenta de servicio, secret-store, firma de solicitudes, aislamiento de Win32 GUI o cierre de la WebUI. El 0037 ensayó SIDs temporales separados, pero esa prueba requiere aprobación explícita para crear cuentas y no se ejecuta aquí.

**Los nonces se guardan solo en memoria y desaparecen si el proceso muere.** El protocolo ficticio de líneas aún necesita límites de lectura/tiempo más estrictos ante un cliente de ese mismo SID que mantenga la conexión abierta. La bitácora persistente del 0046 protege exclusivamente órdenes START de ViewTV dentro de su SQLite ficticia; no se ha conectado al pipe ni al broker productivo. Ningún `ACCEPTED_MOCK` equivale a un POST real, autorización de película, o permiso para borrar archivos.

Antes de activar una retirada real se requieren una cuenta broker Windows no interactiva de **SID independiente**, DACL de IPC y NTFS que excluyan usuarios/procesos lectores y escritores, segregación de credenciales qBit y bloqueo de todas sus vías directas (GUI/WebUI/reinicio), drenaje real Jellyfin/HLS, autorización administrativa independiente por película apta, journal productivo y recuperación tras pérdida eléctrica con verificación de espacio liberado. Todo cambio de cuentas, firewall, ACL, contraseñas, procesos y servicios requiere autorización **expresa de mantenimiento**, sin interferir con torrents ajenos.

El preflight real todavía mantiene **cuatro películas BLOQUEADAS**. Esta nueva pieza es una base de identidad para el futuro broker; **el borrado sigue prohibido**.
