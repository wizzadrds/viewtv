# VIEWTV 0052 — instalación real y reversible de identidad Windows independiente para un broker inerte

**Fecha:** 28/11/2026. **Equipo:** LAPTOP-V2QSMC01. **Autorización de mantenimiento:** el operador autorizó expresamente instalar y probar el broker Windows tras el plan de migración 0051. **Alcance realizado:** instalar y verificar un servicio real de **solo salud**, no un ejecutor de retirada. **Sin autorización individual de ninguna película**, sin cambiar qBittorrent, Jellyfin, WebUI, firewall ni ACL de multimedia.

## Instalación efectuada en el host

Se instaló **`VIEWTV-Broker-0052`** en Windows como servicio de inicio **Manual**, bajo la cuenta integrada **`NT AUTHORITY\LocalService`** (SID `S-1-5-19`). Windows le otorga además el **SID de servicio exclusivo `NT SERVICE\VIEWTV-Broker-0052`** (`sc.exe sidtype ... unrestricted`); el propio servicio comprueba en su token tanto `LocalService` como el grupo SID exclusivo antes de atender.

El instalador colocó el binario compilado de `scripts/viewtv_broker_health_service_0052.cs` únicamente en `C:\ProgramData\VIEWTV-Broker-0052\bin\viewtv-broker-health-0052.exe`, con carpeta de datos privados en `C:\ProgramData\VIEWTV-Broker-0052\data`. La ruta es nueva, fija, con marca exclusiva y exclusión de entradas ajenas/reparse points para su reversión. **La DACL del directorio raíz se protegió antes de crear el ejecutable** para impedir sustituciones por otros usuarios durante la compilación. Las ACL de raíz, binario y datos no admiten herencia, grupos Users/Everyone u otras ACE: únicamente **Administradores, SYSTEM y el SID particular del servicio**. Ese SID solo puede leer y ejecutar el binario; puede modificar exclusivamente su carpeta de estado privada.

El código Windows implementa **una sola petición `HEALTH`** en una tubería local con DACL que autoriza únicamente al SID del servicio y valida el token del cliente mediante `RunAsClient`. Se comprobó una conexión positiva desde el **propio proceso del servicio** y una conexión negativa desde la sesión operadora; la última resultó denegada por Windows. **No existe implementación de STOP, START, lectura de credenciales, API qBit, Jellyfin, borrado NTFS, rutas de medios, ni apertura de sockets externos** en este ejecutable.

Tras la prueba, el servicio **se detuvo y quedó instalado, con inicio manual**. No se registró tarea programada, no se habilitó autoarranque. Esto no detuvo ningún servicio previo; solo el servicio nuevo y exclusivamente de prueba. **Huella SHA-256 del ejecutable que quedó instalado en este equipo:** `abf0ad7020f0139b2440f30e1c7d48dbb32972fd6881290f3973d18cbd193248`, obtenida con `certutil -hashfile` tras la instalación. Es una referencia de integridad para esta compilación local, **no una firma Authenticode ni una garantía de compilación reproducible**.

## Fallos controlados y reversión

Se produjeron fallos durante las primeras compilaciones y comprobaciones (ambigüedad C# de `TimeoutException`, sintaxis de `sc.exe` y de un argumento PowerShell de ACL, salida localizada de `sc.exe qsidtype`, y lectura `ReadTimeout` no compatible con el pipe). **Cada intento fallido activó la reversión automática de su servicio y su directorio exclusivo 0052**, y se comprobó que el sondeo posterior no encontraba esos elementos antes del intento definitivo. Se corrigió el código sin relajar la DACL ni permitir conexiones del operador: la identidad positiva y negativa debían pasar.

`scripts/viewtv_windows_broker_stage_0052.ps1` contiene tres modos fijos:
- `-Mode Probe`: solo lectura, sin cambios;
- `-Mode Install -ApprovedMaintenance`: solo con elevación y aprobación explícita; rechaza servicio o carpeta existente, compila localmente y exige prueba SID + pipe + denegación del operador, luego deja el servicio detenido;
- `-Mode Rollback -ApprovedMaintenance`: requiere elevación y marca del directorio exacta, valida solo nombres permitidos y ausencia de reparse points, detiene exclusivamente `VIEWTV-Broker-0052`, elimina **solo** ese servicio y los archivos 0052 enumerados sin borrado recursivo. No tiene parámetro de ruta arbitraria. Las comprobaciones de reversión han sido ejercitadas con las instalaciones interrumpidas; **no se ha revertido la instalación final aprobada**.

Para revertir la instalación final en una ventana aprobada, ejecutar desde el proyecto:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts\viewtv_windows_broker_stage_0052.ps1 -Mode Rollback -ApprovedMaintenance
```

## Validación independiente de seguridad

`scripts/viewtv_windows_broker_verify_readonly_0052.ps1` no reinicia el servicio; comprueba desde Windows que existe y está parado/manual, su binario exacto, marca del directorio, identidad de servicio distinta de la del operador, **DACL protegida de tres ACE exactas** (Administradores, SYSTEM y SID de servicio) en carpeta raíz, bin, data y exe, escritura prohibida para el SID del servicio sobre el ejecutable y escritura permitida solo en datos, y el registro categórico producido por el self-test del propio servicio. **Todas esas comprobaciones devolvieron PASS**.

`worker/retirement_installed_broker_gate_0052.py` y `scripts/viewtv_broker_instalado_gate_0052.py` requieren dos observaciones exactas de diez líneas Windows, de solo lectura y sin publicar SIDs ni credenciales. **2/2 verificaciones válidas**; retornan **`ESTADO_RETIRADA_0052=BLOQUEADA`, código 3** si ambas pasan y código 2 ante cualquier evidencia incompleta; **nunca código 0**. `backend/tests/test_retirement_installed_broker_gate_0052.py` incluye **53 pruebas** de integridad del informe, condiciones falsas, datos secretos adicionales, rutas inyectadas, ausencia de permisos de unlink y retorno siempre denegatorio.

**Calidad final:** regresión backend completa **2.183/2.183 PASS**, dos advertencias externas de dependencias Starlette/FastAPI; Ruff global `backend worker scripts` PASS; TypeScript y ESLint PASS; smoke HTTP real solo lectura **10/10 PASS**.

**Auditorías reales tras la instalación:** preflight 0018 **4/4 películas bloqueadas**, 2/2 diarios NTFS verificados; qBit 0026 **2/2 torrents no en reposo, 4 extras protegidos** (488 bytes lógicos, no espacio recuperable); interlock 0041 **8/8 fuentes verificadas, seis barreras productivas pendientes, permiso de borrado NO**. Ni películas reales eliminadas ni torrents modificados.

## Límites: qué no significa «broker instalado»

El servicio instalado es una **primera fase real de identidad y canal privado**, no el broker de retirada. Sigue siendo manual y parado, **sin capacidad de controlar qBit, NTFS o Jellyfin**. No sustituye el interlock 0041; cuando este indica `BROKER_WINDOWS_SID_AISLADO_NO_INSTALADO` se refiere al broker **productivo y operativo con garantías sobre File ID/torrents**, no al servicio inerte de salud recién instalado. Las rutas GUI/WebUI de qBit siguen existiendo y el propio qBit y Jellyfin mantienen su identidad operadora. No hay custodia exclusiva por torrent, HLS v2 ni drene de lectores, ni garantía de hardlinks sin terceros, ni autoridad única entre el broker y SQLite, ni prueba de apagón y recuperación real de espacio.

La cuenta integrada LocalService **no es una credencial privada secreta** y un administrador elevado puede recuperar el acceso al sistema. El aislamiento ensayado utiliza el **SID particular de servicio en la DACL**, no la mera pertenencia a LocalService. La prueba de HEALTH solo afecta a este servicio; un actor con control de administración puede administrar servicios.

**Para autorizar borrado físico** hará falta, además del mantenimiento, que todos los perfiles activos marquen vista **una película exacta** y que un administrador independiente apruebe esa misma película una vez verificada elegibilidad. Las cuatro actuales no son aptas. No atribuir esa aprobación a una autorización general de mantenimiento. **No fusionar PR #2 ni abrir accesos qBit/Jellyfin o modificar ACL de medios solo porque se instaló el servicio de salud.**
