# VIEWTV 0047 — tubería Win32 con DACL exclusiva y token restringido (laboratorio)

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`, PR #2 OPEN/DRAFT sin fusión. **Sin instalar broker, crear cuentas, cambiar ACL productivas, parar torrents, enviar HTTP a qBittorrent ni borrar películas.**

## Por qué esta prueba importa

El 0037 demostró que dos identidades Windows no administradoras, creadas temporalmente durante un ensayo autorizado, podían separarse mediante ACL y que el broker ficticio podía retirar exactamente dos nombres NTFS. La auditoría 0040 constató que **qBittorrent nativo comparte el SID de la sesión operadora** y que su WebUI y firewall permiten posibles accesos externos. El 0046 resolvió en SQLite la intención de START, pero **GUI/WebUI no consultan esa base de datos**.

La barrera que ahora se prueba es distinta: **el kernel Windows niega la conexión a un canal de control local si el token no tiene habilitado el SID incluido en su DACL**, antes de recibir ninguna orden. Esto podría ser una futura entrada de un broker de identidad separada; por sí solo **no aísla la GUI ni el proceso qBit de producción**.

## Implementación del ensayo sin cuentas efímeras

`scripts/test_viewtv_windows_pipe_sid_sandbox_0047.ps1`:

- Crea únicamente una instancia efímera `NamedPipeServerStream` cuyo nombre incorpora un GUID aleatorio. **No crea socket TCP, servicio, tarea programada, usuario local, directorio, fichero ni regla firewall**. Un bloque `finally` libera el pipe y todos los handles. No tiene parámetros que permitan seleccionar películas, credenciales o rutas.
- Usa `PipeSecurity` con herencia de DACL deshabilitada y una sola ACE explícita **Allow FullControl para el SID actual**. Comprueba que el descriptor Win32 contiene exactamente esa ACE. Esta prueba se ejecuta bajo el operador del ensayo, **no bajo un SID broker productivo**.
- Obtiene un token restringido del proceso mediante `OpenProcessToken` y `CreateRestrictedToken`, **deshabilitando el SID actual para concesiones de acceso**. Bajo su suplantación intenta conectar al pipe y comprueba que **Windows deniega el acceso**. A continuación, el token no restringido conecta y transmite un comando ficticio `START` con hash sintético de 40 caracteres.
- El parser de prueba permite solamente ese hash sintético y **deniega `START all`**. El ensayo no crea un proxy a qBittorrent, ni emite una llamada WebUI real. Esto prueba de forma acotada la validación del contrato, no una política productiva compleja ni protección contra un cliente externo con el mismo SID.

`worker/retirement_pipe_sid_gate_0047.py` valida **diez líneas ASCII exactas**, rechaza datos extra, duplicados, secretos, SIDs, permisos físicos positivos y respuestas erróneas. `scripts/viewtv_retirada_pipe_sid_0047.py` llama dos veces al ensayo de Windows desde WSL, sin pasar argumentos del usuario, con tiempo límite, captura limitada y sin exponer salidas privadas. Siempre termina **código 3** si ambos informes se verifican pero falta aislamiento productivo, o **código 2** si falla cualquiera; **nunca devuelve código 0**.

## Resultados comprobados

La ejecución directa del script Windows confirmó:

- `PIPE_ACL_UNICAMENTE_SID_DESIGNADO=PASS`
- `TOKEN_RESTRINGIDO_NO_CONECTA=PASS`
- `ORDEN_START_ALL_RECHAZADA_POR_POLICY=PASS`
- `SID_PERMITIDO_SOLO_HASH_SINTETICO=PASS`
- `GUI_WEBUI_QBIT_PRODUCCION_AISLADA=NO`
- `BROKER_PRODUCTIVO_INSTALADO=NO`
- `CUENTAS_LOCALES_CREADAS=0`
- `ACL_PRODUCTIVAS_MODIFICADAS=0`
- `POST_QBIT_REAL=0`
- `ARCHIVOS_REALES_ELIMINADOS=0`

El runner independiente WSL **validó 2/2 ensayos Windows** y devolvió `ESTADO_RETIRADA_0047=BLOQUEADA`, permiso NO y cuatro barreras futuras explícitas. Se añaden **47 pruebas unitarias** en `backend/tests/test_retirement_pipe_sid_gate_0047.py`, que cubren informes falsificados, secretos, estados positivos ilegítimos, ejecución del runner sin shell, nombres de distribución WSL inyectados, fuentes incompletas y salida no cero obligatoria.

**Calidad general verificada:** regresión backend **1.899/1.899 PASS**, dos advertencias externas de Starlette/FastAPI, ejecutada en Docker sin red y con el repositorio montado solo lectura. **Ruff global** `backend worker scripts` PASS; **TypeScript PASS, ESLint PASS**, smoke HTTP real de solo lectura **10/10 PASS**. **Auditoría Windows del 0047: 2/2 ensayos válidos**, evaluador Python **47/47 PASS**. Preflight real 0018: **4/4 películas BLOQUEADAS, 2/2 diarios NTFS verificados**. Custodia qBit real 0026: **dos torrents no en reposo seguro**, seis archivos inspeccionados, cuatro extras protegidos (488 bytes lógicos). Interlock 0041: **8/8 informes verificables pero seis barreras de producción PENDIENTES**, permiso de borrado NO, cero archivos eliminados y cero torrents modificados. No se usan credenciales del qBit host ni se modifica ningún directorio multimedia.

## Lo que todavía NO demuestra

**La ACL de este ensayo protege una tubería creada por el mismo SID del operador.** Un proceso externo que pueda usar **ese mismo SID** también podría conectarse; esta prueba deshabilita artificialmente el SID en un token restringido, pero **no ha demostrado un proceso broker independiente y no interactivo con SID distinto**. Tampoco se ha conectado el canal a `stop/start` de qBit, ni se ha trasladado su configuración/credenciales a custodia exclusiva, ni se ha revocado el acceso de GUI/WebUI, reinicios autónomos o conexiones LAN. No existe un broker productivo por ejecutar este script.

El futuro paso real requiere una ventana de mantenimiento y autorización expresa: separar el SID no interactivo del broker, inventariar clientes legítimos qBit, migrar claves sin divulgarlas y con reversión, crear una DACL del pipe **y del File ID NTFS** realmente exclusiva, asegurar que solo el broker puede reiniciar el hash objetivo y drenar Jellyfin/HLS. Luego consumir una firma administrativa de una película apta dentro del journal Windows único, con recuperación de fallos y verificación de bloques físicos. **No cambiar firewall, cuentas, ACL, secretos o servicios activos sin consentimiento específico.**

El interlock 0041 y el preflight real siguen bloqueando las cuatro películas, sin candidatas administrativas. **El ensayo del 0047 NO autoriza ningún borrado físico.**
