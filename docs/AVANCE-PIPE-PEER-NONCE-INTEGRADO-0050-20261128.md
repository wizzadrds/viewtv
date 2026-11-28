# VIEWTV 0050 — unir identidad de pipe Win32 y nonce durable en una misma petición

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`; PR #2 abierta y en borrador, sin merge ni despliegue. **Solo Windows TEMP y tuberías IPC de GUID**; no se crea ninguna cuenta, servicio, ACL de medios, regla de firewall, clave ni sesión de qBittorrent.

## Qué corrige

El 0048 validaba el SID del cliente en el servidor mediante `NamedPipeServerStream.RunAsClient` y rechazaba payloads y nonces repetidos **en memoria**. El 0049 probaba en otro script que un nonce escrito con `WriteThrough` y `Flush(true)` sobrevivía a la muerte del proceso, pero no lo vinculaba **a la conexión Win32 verificada**. El 0050 integra ambos controles, en un único ensayo de petición ficticia: **identidad de peer comprobada por el kernel → formato y hash objetivo validados → intención de nonce persistida → respuesta MOCK o muerte abrupta**.

El primer hijo se termina realmente **después de escribir la intención y antes de enviar respuesta**. Otro proceso levanta **una nueva tubería** y repite exactamente la petición: debe recibir rechazo y no volver a registrar la intención.

## Implementación

`scripts/test_viewtv_windows_pipe_peer_nonce_sandbox_0050.ps1`:

- Genera un directorio propio `TEMP/viewtv-0050-ficticio-<guid>`, con marca estricta y solo tres nombres de intención enumerados por GUID y SHA256; rechaza directorios y archivos reparse point, entradas externas o nombres inesperados. El modo raíz `Test` no acepta un ID del usuario. Los únicos modos hijos aceptan un GUID en formato estricto, no rutas suministradas.
- Cada hijo crea una tubería `NamedPipeServerStream` con nombre GUID, **DACL sin herencia y una única ACE para el SID del operador del laboratorio**. El cliente propio conecta con nivel de suplantación `Impersonation`; **el servidor** invoca `RunAsClient` + `WindowsIdentity.GetCurrent(true)` para comprobar el SID que proporciona Windows, sin confiar en un campo `SID=` del mensaje. Un parámetro exclusivamente de prueba fuerza una respuesta `DENIED_IDENTITY` para validar el rechazo de identidad no verificada; **no es otro usuario real**.
- El protocolo acepta únicamente `VT50|MOCK_START|<40 hex>|<32 hex>` y comprueba el hash objetivo sintético exacto. `START all`, hash ajeno o un `SID=` adicional no son aceptables. Ninguna petición llega a qBittorrent.
- La reserva usa `FileMode.CreateNew` sobre el nombre de nonce, `FileOptions.WriteThrough`, `Flush(true)` y un registro con comando sintético, hash, nonce y **SHA256 del SID de la identidad Windows local**, en lugar del SID en claro. El resultado `ACCEPTED_MOCK` **solo se genera después de ese flush**. Una entrada existente coherente es `DENIED_REPLAY`; incompleta, alterada o temporalmente inaccesible es `DENIED_INTEGRITY`. Ninguno de esos resultados vuelve a ejecutar una orden.
- La primera operación de prueba termina su proceso hijo mediante `TerminateProcess(GetCurrentProcess(),90)` inmediatamente después de persistir la intención, **antes de responder por la tubería**. El proceso padre valida el registro y arranca otro hijo con una tubería y un proceso distintos.
- Se verifican sucesivamente replay tras reinicio, SID falso en payload, hash ajeno, rechazo de identidad no verificada, nonce nuevo, carrera entre **cuatro pares cliente/servidor de tubería** sobre un nonce común con **un único ganador**, y rechazo de diario falsificado. Los perdedores de la carrera pueden observar `DENIED_INTEGRITY` mientras se escribe el registro; eso también es una denegación, y la comparación final del registro completo comprueba la identidad del ganador.
- Al terminar se borran exclusivamente los nombres de prueba enumerados y el directorio propio con `Directory.Delete(...,false)`, sin borrado recursivo. El script no posee parámetros de paths de medios ni funciones de eliminación real.

`worker/retirement_pipe_nonce_gate_0050.py` valida de forma exacta los trece resultados ASCII; cualquier añadido, falso permiso o dato secreto bloquea. `scripts/viewtv_retirada_pipe_nonce_0050.py` ejecuta la prueba **dos veces** desde WSL, no acepta argumentos, exige el contrato fijo y termina **3** si ambas pruebas son válidas, **2** si una falla; **nunca 0**. El resultado siempre es `ESTADO_RETIRADA_0050=BLOQUEADA` y autorización NO.

`backend/tests/test_retirement_pipe_nonce_gate_0050.py` contiene **56 pruebas** que comprueban fuentes completas e incompletas, duplicaciones, afirmaciones de autorización imposibles, inyección del nombre de distro, control de comandos del runner y su código de salida bloqueante.

## Evidencia Windows

La ejecución nativa directa devolvió los indicadores `SID_PEER_Y_COMMIT_ANTES_DE_CRASH=PASS`, `REPLAY_EN_NUEVA_PIPE_DENEGADO=PASS`, `SID_FALSO_EN_MENSAJE_DENEGADO=PASS`, `HASH_AJENO_DENEGADO=PASS`, `IDENTIDAD_NO_VERIFICADA_DENEGADA=PASS`, `NONCE_NUEVO_ACEPTADO_SOLO_MOCK=PASS`, `CUATRO_PIPE_CLIENTS_UNICA_RESERVA=PASS`, `JOURNAL_MANIPULADO_FALLA_CERRADA=PASS`, `SANDBOX_GUID_LIMPIADO=SI`; y consta explícitamente `BROKER_PRODUCTIVO_INSTALADO=NO`, `QBIT_REAL_CONTACTADO=NO`, `ARCHIVOS_REALES_ELIMINADOS=0`, `TORRENTS_REALES_MODIFICADOS=0`.

El runner WSL verificó **2/2 ejecuciones Windows independientes** y devolvió BLOQUEADA sin conceder permiso. **56/56 pruebas nuevas PASS**; **backend completo 2.059/2.059 PASS** (2 advertencias externas Starlette/FastAPI, Docker sin red y código fuente montado solo lectura), Ruff global `backend worker scripts` PASS, TypeScript PASS, ESLint PASS y smoke HTTP real solo lectura **10/10 PASS**. Tras endurecer la lectura concurrente de la bitácora, se repitieron el ensayo Win32 directo **PASS** y el runner WSL con **2/2 informes válidos**, estado BLOQUEADA y permiso físico NO. Auditorías reales: preflight 0018 **4/4 películas BLOQUEADAS y 2/2 diarios NTFS válidos**; admin 0019 **0 candidatas y 0 aprobaciones**; custodia 0026 **2/2 torrents no seguros y 4 extras protegidos (488 bytes lógicos)**; interlock 0041 **8/8 informes coherentes, 6 barreras productivas pendientes**, sin borrados ni modificaciones qBit.

## Lo que todavía NO está hecho

**El cliente y servidor de este ensayo utilizan el mismo SID del operador**, y la DACL no impediría que otro proceso con ese SID estableciera conexión. No existe todavía servicio broker bajo cuenta no interactiva distinta, ACL NTFS exclusiva, ni control de GUI/WebUI/reinicio autónomo del qBit host. Esta prueba se limita a un **comando mock**: nunca recibe ni ejecuta una orden real. El `ReadLine` del ensayo es acotado por el tiempo máximo del proceso de prueba, **no está endurecido contra un cliente persistente que retenga una tubería abierta**; un broker productivo necesita lectura incremental limitada, timeouts y cierre de sesiones.

La intención en archivo temporal con `Flush(true)` **no prueba orden durable ante apagón eléctrico ni aislamiento frente a procesos del mismo SID**. Sigue faltando una transacción de autoridad unificada con la SQLite de qBit 0045/0046, broker Windows bajo identidad propia, exclusión efectiva de terceros hardlinks/escritores, Jellyfin/HLS v2 admitido y drenado, autorización administrativa individual y prueba de espacio físico liberado tras retirada.

El interlock 0041 continúa con **seis barreras productivas pendientes** y las **cuatro películas reales bloqueadas**, sin candidatas aptas. **No habilitar borrado productivo ni fusionar/desplegar la PR sin aprobación expresa del usuario y de una película elegible y autorizada.**
