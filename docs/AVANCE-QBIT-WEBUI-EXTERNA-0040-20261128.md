# VIEWTV 0040 — WebUI/GUI qBittorrent: evidencia real de accesos fuera del cerco

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`; PR #2 OPEN/DRAFT, no fusionar. **Alcance:** auditoría Windows estrictamente solo lectura + evaluador Python fail-closed + tests. No cambian Jellyfin, qBittorrent, Windows Firewall, ACL, tareas, perfiles, películas ni torrents.

## Objetivo: completar la evidencia que falta después del 0039

El 0038 registró durablemente un `stop` ficticio por hash; el 0039 serializó `start_torrent` del worker VIEWTV con esa misma SQLite en `MockTransport`. El propio test 0039 demostró que otro cliente WebUI puede seguir emitiendo `start` directamente, ignorando el diario. Esta fase inventaría **la instancia real de qBittorrent y las rutas de acceso a la WebUI/GUI** para impedir que una «parada observada» se convierta accidentalmente en autorización física.

## Herramientas nuevas

- `scripts/viewtv_windows_qbit_webui_readonly_0040.ps1`, PowerShell sin parámetros: consulta **un proceso nativo qBittorrent**, SID de su dueño por CIM, sockets TCP escuchando y conexiones establecidas cuyo puerto local es el de WebUI, y reglas de firewall ActiveStore `Allow` por aplicación/rango. **No** imprime PID, SID, puertos de clientes, direcciones, ruta de ejecutable ni conexiones individuales.
- Lee el fichero local `qBittorrent.ini` **sin copiarlo**; inspecciona únicamente la sección `[WebUI]` y emite si `Enabled`, `APIKey` y `Password_PBKDF2` están configurados. **Jamás imprime los valores, claves ni hashes**. Al no demostrar que la instancia activa usa ese mismo perfil de configuración, declara explícitamente `WEBUI_CONFIG_VINCULADA_A_PROCESO=NO_VERIFICADA`. También declara sin verificar identidad exclusiva del secreto del broker, capacidad de la GUI de reanudar y ausencia de escritores NTFS. Si faltan fuentes devuelve `INCOMPLETA`, código distinto de cero y borrado NO.
- `worker/retirement_qbit_webui_gate_0040.py`: contrato cerrado para 16 campos exactos o formato canónico `INCOMPLETA`. Rechaza datos extras, duplicaciones, informaciones secretas, SIDs, rutas, un supuesto permiso positivo, la ambigüedad de instancia, campos con espacios y salida truncada. Compara dos instantáneas nativas, marca cambios y **nunca otorga custodia exclusiva ni borrado**, incluso si WebUI aparece deshabilitada y los puertos dejan de escucharse.
- `scripts/viewtv_retirada_webui_qbit_0040.py`: ejecuta **dos auditorías Windows** desde WSL con tiempo de espera y tamaño acotados. Muestra solo razones categóricas; fallo de uno de los procesos => `ESTADO_RETIRADA_0040=BLOQUEADA`, `PERMISO_DE_BORRADO_OTORGADO=NO`, 0 archivos eliminados y 0 torrents modificados.
- `backend/tests/test_retirement_webui_qbit_0040.py`: pruebas sin red de informes realistas, ausencia de puertos, credenciales configuradas, variación entre auditorías, fuente incompleta, filtración de secretos, campos inconsistentes, falsos positivos de autorización y fallos del orquestador.

## Evidencia real del portátil (solo lectura)

La primera auditoría Windows devolvió `OBSERVACION_SOLO_LECTURA`; el orquestador hizo **dos observaciones** adicionales y terminó `ESTADO_RETIRADA_0040=BLOQUEADA`. Se encontraron:

| Comprobación | Valor |
|---|---|
| Proceso qBittorrent nativo único | Sí |
| qBittorrent comparte SID con la sesión operadora | **Sí** |
| WebUI habilitada según la configuración examinada | **Sí** |
| Clave API y hash de contraseña configurados | **Sí, ambos presentes**, sin revelar valores |
| Listener de qBittorrent accesible fuera de loopback | **Sí** |
| Reglas de firewall amplias para la aplicación | **Sí** |
| Conexión TCP establecida desde fuera de loopback al puerto WebUI en ese instante | No observada |
| ¿La configuración examinada es necesariamente la que usa el proceso? | **No verificado** |
| ¿Solo el broker dispone de acceso de control y la GUI no puede reanudar? | **No verificado** |
| ¿Los dos enlaces NTFS están excluidos de nuevos escritores/terceros? | **No verificado** |
| ¿Puede retirarse físicamente una película? | **NO** |

**Interpretación estricta:** la presencia de una contraseña o clave API no prueba exclusividad de la interfaz ni revocación de otros clientes; una ausencia de sesión remota observada no prueba inaccesibilidad desde LAN, y un cierre del puerto tampoco impide una reanudación desde GUI o por otro mecanismo con el mismo SID. No se han consultado contraseñas al servidor, enviado POSTs de inicio/parada, ni comprobado reachability desde LAN con otro dispositivo.

## Antes de aislar qBittorrent real — secuencia que requiere autorización de mantenimiento

1. **Respaldar y verificar reversión** de configuración y reglas qBit/WebUI, ACL de medios y programador del publicador, en lugar privado fuera de Git. Inventariar clientes legítimos que usan la WebUI, incluido el worker VIEWTV, **sin copiar contraseñas a logs**. Confirmar desde LAN quién necesita acceso. No asumir que `127.0.0.1` impide que otros procesos locales accedan.
2. Crear un **broker Windows no interactivo con SID independiente** y autoridad de start/stop y secretos custodiados fuera del perfil GUI. Migrar el cliente qBit y sus credenciales con una transición verificable. Cualquier identidad GUI, tarea o cliente externo con las mismas capacidades debe perder la posibilidad de iniciar **el torrent objetivo**; bloquear solo los endpoints del worker no basta.
3. **Cerrar canales alternativos**: GUI, WebUI desde otros procesos y usuarios, ejecución de tareas, accesos externos/host y reinicio de qBit. Mantener reproducción y descargas ajenas; validar pruebas negativas de `start` desde identidad no autorizada **durante toda la transacción** (también en reinicios/errores). Proteger el File ID objetivo con ACL/handles de Windows y descartar terceros hardlinks. Nunca parar todos los torrents ni alterar cuatro extras de 488 bytes lógicos.
4. Con una sola película **apta por marcas de vista, solicitud, estado de descarga, diario NTFS y admin independiente**, registrar intención durable y parar **solo su hash exacto**. Completar doble confirmación qBit + identidad NTFS, sin carreras, y acreditar que solo el broker puede ordenar reinicios; si falla, bloquear y reconciliar.
5. Aún falta la autorización administrativa firmada consumida una vez, drenaje real de Jellyfin directo/HLS v1, ejecutor Windows transaccional con rollback tras muerte abrupta/reinicio y medición de bloques físicos liberados. Ninguna de estas garantías se infiere del 0040.

**Resultado:** auditoría de la vía exterior WebUI/GUI funcionando sobre Windows real, contrato de reporte sin secretos y barrera de borrado explícita. **El aislamiento efectivo de producción NO está aplicado y no se autoriza todavía la retirada física.** Samsung TV y Momentos siguen pospuestos hasta acabar esta prioridad.

## Cierre de calidad verificado

- **35/35 pruebas dirigidas del hito 0040 PASS**: informes manipulados y sin datos, credenciales configuradas que no equivalen a exclusividad, discrepancias entre observaciones, validación de ausencia de secretos, errores en el runner.
- **Suite backend íntegra 1704/1704 PASS**, en Docker offline con código montado read-only, **2 advertencias de dependencias externas Starlette/FastAPI**; no hay fallos.
- **Ruff global** `backend worker scripts` PASS (0 errores), **TypeScript PASS, ESLint PASS**, smoke HTTP real read-only **10/10 PASS**.
- **Preflight real 0018**: 4/4 películas bloqueadas, 2/2 diarios NTFS verificados, autorización NO, cero archivos borrados y cero torrents modificados. **Custodia real qBit 0026 solo GET**: 2/2 torrents sin reposo seguro, 2 archivos publicados correlacionados, 4 extras protegidos (488 bytes lógicos).
- Auditoría Windows WebUI real ejecutada y doble lectura del runner 0040 concordante; `ESTADO_RETIRADA_0040=BLOQUEADA`. No se han cambiado cuentas, ACL, puertos, API keys ni configuración del cliente. No se ha probado reachability desde un cliente LAN ni se ha instalado un broker de custodia.
