# VIEWTV 0037 — aislamiento de identidades Windows y permisos NTFS

**28/11/2026 — Rama:** viewtv-seguimiento-descargas-0012. **PR #2:** abierta y en borrador, sin fusionar. **Alcance:** prueba de mecanismo de separación SID/ACL exclusivamente con archivos ficticios y cuentas efímeras, auditoría real solo lectura, evaluador de bloqueo. Nada desplegado en producción.

## Qué faltaba

El 0034 probó que CreateHardLinkW puede crear un tercer enlace NTFS incluso durante FileShare.None y dos handles DELETE. El 0036 exige exactamente dos enlaces en la auditoría, pero la comprobación no impide crear otro después. Es necesario proteger **la capacidad de modificar los nombres del File ID**, no solo las lecturas. La identidad del broker debe estar separada de las aplicaciones que sirven o descargan películas.

## Ensayo Windows con DOS SIDs reales separados

Se amplió scripts/test_viewtv_windows_distinct_sids_sandbox.ps1, que exige -AuthorizeEphemeralAccounts. El nuevo runner scripts/test_viewtv_windows_retirada_sids_sandbox_0037.ps1 exige -AutorizarCuentasEfimeras, verifica 20 etiquetas de resultados y constata cero cuentas residuales.

- Dos cuentas locales no administrativas temporales tienen tokens distintos. El lector puede leer los bytes de un vídeo totalmente ficticio en una carpeta GUID privada. El broker tiene control completo del mismo material.
- El lector **no puede crear otro hardlink ni en la carpeta sellada ni en un directorio propio donde tiene Modify**, porque el fichero fuente tiene una DACL de solo lectura para ese SID. El broker sí puede crear enlaces en el sandbox.
- El broker, actuando con su propio SID, abre ambos nombres ficticios con DELETE + FILE_READ_ATTRIBUTES y FILE_SHARE_DELETE. El lector no puede abrir nuevos lectores ni crear un hardlink en su directorio mientras el broker mantiene ambas reservas.
- El broker completa dos unlinks ficticios mediante SetFileInformationByHandle(FileDispositionInfoEx), con ambos handles vivos; ambos nombres dejan de existir. El ensayo anterior también verificó bloqueo ante escritor preabierto y la custodia de configuración privada.
- Resultado real: SIDS_DISTINTOS_NO_ADMINISTRADORES=PASS; LECTOR_PUEDE_LEER_ARCHIVO=PASS; LECTOR_NO_CREAR_HARDLINK_EN_DIRECTORIO_PROPIO=PASS; LECTOR_NO_CREAR_HARDLINK_DURANTE_COMMIT=PASS; BROKER_DISTINTO_SID_DOS_UNLINKS_FICTICIOS=PASS; CUENTAS_TEMPORALES_REVERTIDAS=PASS.
- **Cero archivos reales borrados; cero torrents modificados; cero permisos productivos modificados.** Las cuentas temporales se crearon con nombres aleatorios y se retiraron al terminar. El ensayo NO equivale a un servicio instalado, ni a recuperación ante apagón, ni a una autorización productiva.
- Respaldo privado del script de SIDs previo a 0037, sin subir a Git: /home/viewtv/viewtv-backups/0037-20261128/test_viewtv_windows_distinct_sids_sandbox_ANTES.ps1; SHA256 8041f5e15cfd45b4766c99edbad7501f3e4373ff32fb39ec788f5a1de4c7e36f.

## Auditoría del equipo real, sin cambiarlo

scripts/viewtv_windows_sids_acl_readonly_0037.ps1 consulta por CIM GetOwnerSid los procesos Jellyfin/qBit y la identidad de la tarea del publicador. Comprueba solo la protección de herencia de cuatro directorios raíz. No emite nombres, contraseñas, títulos, rutas de películas ni hashes. Observaciones:

| Condición | Resultado |
|---|---|
| Operador con sesión elevada | Sí |
| Jellyfin nativo con SID del operador | Sí |
| qBittorrent nativo con SID del operador | Sí |
| Publicador programado con SID del operador | Sí |
| Raíces con herencia ACL bloqueada | **1 de 4** |
| Cuentas efímeras residuales | **0** |
| Broker productivo con identidad distinta | **No verificado** |
| Exclusión kernel del File ID productivo | **No verificada** |
| Permiso de borrado | **NO** |

La herencia ACL, por sí sola, no demuestra los permisos efectivos de una película. Que Jellyfin/qBit compartan identidad no exige migrar ahora ambos servicios: podría restringirse **solo la película a retirar** bajo un broker separado, pero únicamente cuando el torrent exacto esté inmovilizado, no haya handles anteriores y los lectores sigan teniendo acceso de solo lectura. Hoy no se cumplen esas condiciones.

## Gate de software 0037, siempre cerrado

- worker/retirement_sid_gate_0037.py: contrato estricto para salida de Windows. Rechaza campos secretos o extras, duplicados, estados alterados, falsos permisos, ausencia de datos y discrepancias; aun si una futura lectura dice que todos los procesos tienen otros SIDs, no confunde ello con aislamiento probado por File ID.
- scripts/viewtv_retirada_sids_gate_0037.py: hace dos auditorías nativas Windows desde WSL con tiempo límite y publica solo motivos agregados. Resultado real: ESTADO_RETIRADA_0037=BLOQUEADA. Sus motivos incluyen qBit/Jellyfin/publicador sin segregar, herencia de ACL, broker no enrolado y ausencia de pruebas kernel.
- backend/tests/test_retirement_sid_gate_0037.py: **29 pruebas aisladas PASS** de validación estricta, escenarios positivos observacionales y fallos cerrados.
- **Regresión completa final:** backend 1601/1601 PASS en Docker sin red con fuentes read-only (2 advertencias de dependencias Starlette/FastAPI); Ruff global backend/worker/scripts PASS; TypeScript PASS; ESLint PASS; smoke HTTP solo lectura 10/10 PASS; prueba Windows NTFS 0034 de dos suites PASS. Preflight real 0018: 4/4 películas bloqueadas, 2 diarios NTFS validados, 0 borrados y 0 cambios a torrents. Tarea del publicador Windows Ready y último resultado 0.
- Incidencia del *runner de laboratorio* corregida: la primera variante lanzó un PowerShell anidado que quedó retenido; se terminó **solo ese proceso propio**, se verificó que no quedaron cuentas efímeras, y se cambió a invocación en el mismo proceso. La ejecución definitiva del runner pasó y revalidó ausencia de cuentas.

## Cómo efectuar el cambio productivo de forma segura — TODAVÍA NO EJECUTADO

1. Obtener ventana de mantenimiento y respaldo/rollback comprobado de las DACL y de la configuración de la tarea/Jellyfin/qBit. Dar de alta una **cuenta Windows exclusiva del broker**, con credencial custodiada por el sistema y sin inicio de sesión interactivo ni permisos globales sobre otros medios.
2. Probar en un File ID real de una película **apta y expresamente elegida** que el operador/Jellyfin sigan leyendo, que el proceso qBit del torrent exacto no pueda escribir ni reanudar, y que la cuenta lectora no pueda ejecutar CreateHardLinkW incluso desde una carpeta propia. No modificar ACL de toda la biblioteca ni de los metadatos extras.
3. Cerrar todas las vías directas Jellyfin/HLS antiguas y garantizar drenaje; tomar una reserva única con el publicador y verificar el mismo diario, las dos rutas, volumen, File ID, número exacto de enlaces, DACL y ausencia de escritores preabiertos bajo el broker.
4. Exigir autorización offline administrativa específica de película/descarga, consumo único, journal privado robusto con pruebas de muerte abrupta y recuperación, dos unlinks bajo handles del broker y medición del volumen antes/después; rollback si falla la preparación.
5. La última consulta real mantiene **4/4 películas BLOQUEADAS** por perfiles sin vista, peticiones, identidad del torrent o autorización; no hay candidata elegible. **No ejecutar borrado ni desplegar permisos productivos sin cumplir todas las barreras.**

**Estado:** el mecanismo de identidades y ACL quedó demostrado en sandbox; la producción sigue con identidades compartidas y no hay broker de retirada instalado. La barrera de borrado permanece cerrada. No se fusiona la PR ni se da por terminado el sistema completo.
