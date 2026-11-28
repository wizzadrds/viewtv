# VIEWTV 0033 — auditoría Windows externa y bloqueo por evidencia incompleta

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`; PR #2 **OPEN/DRAFT**, no fusionar. **Tipo:** comprobación real estrictamente de solo lectura + evaluador conservador. **No hay cambio de producción ni permiso de borrado.**

## Propósito

El 0032 integró HLS v2 en handlers reales **solo bajo TestClient**, pero una película todavía puede estar abierta fuera de ViewTV, por Jellyfin Windows, Docker, qBittorrent u otro lector de un hardlink/original NTFS. Se precisa una evidencia repetible del entorno Windows y una decisión cerrada ante fuentes contradictorias o ausentes. Esta etapa NO instala un guardián de kernel ni autoriza la retirada física.

## Implementación

1. `scripts/viewtv_windows_accesos_externos_readonly_0033.ps1` — PowerShell sin parámetros, únicamente llamadas GET/inventario: `Get-NetTCPConnection`, `Get-Process`, `Get-NetFirewallRule` y filtros de aplicación, puerto y direcciones. Compara listeners IPv4/IPv6 con identidad de proceso y reglas `Allow` habilitadas por aplicación. Su salida limita los valores a indicadores; **no imprime títulos, rutas multimedia, IPs de clientes, hashes de torrents, credenciales ni perfiles**. En caso de error informa `INCOMPLETO` y `PERMISO_DE_BORRADO_OTORGADO=NO`. No reinicia procesos ni cambia firewall.
2. `worker/retirement_external_gate_0033.py` — parser de esquema cerrado y denegación por defecto: rechaza campos repetidos/extra, datos no públicos, truncamientos, caracteres no válidos, estados falsos de verificación de kernel/custodia, conteos de borrados distintos de cero y cualquier intento de afirmar permiso. Contrasta dos observaciones y reporta variaciones y fuentes no verificables. **Todas** las rutas terminan `estado=bloqueada` y `permiso_de_borrado_otorgado=False`, incluso si ambos informes dicen que no hay puertos expuestos: la prueba de red NO equivale a exclusión NTFS.
3. `scripts/viewtv_retirada_accesos_gate_0033.py` — orquestador de solo lectura WSL que llama dos veces al auditor nativo de Windows, con tiempos acotados y comprobación de salida, sin argumentos de película ni credenciales; imprime exclusivamente motivos agregados. Fallo => bloqueo con código de error. **No se conecta al ejecutor de borrado**, no cambia SQLite productiva.
4. `backend/tests/test_retirement_external_gate_0033.py` — pruebas aisladas de exposición realista, ausencia aparente de puertos, discrepancias entre lecturas, fuente incompleta y entradas hostiles (campos extra, duplicados, alteraciones, secretos, tamaños, no ASCII y afirmaciones de permiso).

## Evidencia real en el portátil, solo lectura

El auditor 0033 ha devuelto `ACCESOS_EXTERNOS_0033=AUDITORIA_SOLO_LECTURA`: Jellyfin nativo escucha en todas las interfaces (exposición de listener), hay reglas `Allow` amplias por aplicación Jellyfin, qBittorrent escucha externamente y existen reglas `Allow` amplias para él. El proxy Docker Jellyfin aparece solamente en loopback local (`8097`). El comando WSL ejecutó **dos auditorías** y terminó en `ESTADO_RETIRADA_0033=BLOQUEADA`, con motivos de cortafuegos, Jellyfin, qBit, exclusión NTFS sin demostrar, custodia qBit pendiente, drenaje externo pendiente y autorización administrativa no evaluada.

**Limitación de alcance:** un listener o regla `Allow` NO demuestra conexión remota exitosa desde LAN (faltan cortafuegos superpuestos, redes y pruebas desde cliente), ni permite saber si Jellyfin nativo sirve la misma película. Una auditoría que deja de ver un puerto tampoco demuestra aislamiento integral; la confirmación debe proteger el mismo File ID/descarga exacta hasta terminar la retirada. Este auditor no proporciona esa protección.

**Acciones destructivas reales realizadas:** ninguna. Las fuentes 0033 son consultas del sistema y los evaluadores Python no invocan borrados/pausas. No se han cambiado ACL, reglas de cortafuegos, Jellyfin, qBit, cachés, ficheros originales, torrents ni cuatro metadatos auxiliares.

## Calidad y pendientes

- Las pruebas unitarias del nuevo parser: **17/17 PASS**, tanto en ejecución aislada como en el entorno de pruebas de VIEWTV; Ruff de los módulos nuevos, sin caché: **PASS**.
- **Backend íntegro: 1572/1572 PASS** en Docker sin red con código de repo montado read-only, dos advertencias de dependencias Starlette/FastAPI. **TypeScript PASS**, **ESLint PASS** y smoke HTTP real en solo lectura **10/10 PASS**.
- Preflight real `0018` ejecutado tras 0033: **2/2 diarios NTFS verificados**, **4/4 películas bloqueadas**, `PERMISO_DE_BORRADO_OTORGADO=NO`, 0 archivos eliminados y 0 torrents modificados. Ninguna de las pruebas constituye autorización de borrado.
- Reserva Ruff histórica: **128 hallazgos globales** fuera de los ficheros nuevos; sin solución todavía, no se declara el repositorio completamente verde.

Para avanzar hacia borrado real aún falta un mecanismo efectivo para cerrar accesos directos Jellyfin compatible con TV/LAN, impedir nuevas escrituras y reanudaciones de **un torrent específico**, demostrar exclusión kernel de originales y hardlinks NTFS por File ID, revalidar la identidad exacta en transacción, enrolar administrador y construir ejecutor durable con rollback y medición de espacio liberado. **Sin esta evidencia, nadie debe borrar una película**, aunque la auditoría informe `NO` en todos los puertos.

**PR #2 se conserva en borrador. Primero terminar gestión de espacio y borrado; Samsung y Momentos siguen pospuestos.**
