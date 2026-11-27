# VIEWTV 0031 — capacidades HLS por identidad y generación (laboratorio)

**Fecha:** 27/11/2026 (Europe/Madrid). **Rama:** `viewtv-seguimiento-descargas-0012`; PR #2 permanece OPEN/DRAFT, sin fusionar. **Alcance:** código fuente y pruebas offline; inspección de red de solo lectura. **No se ha cambiado el despliegue productivo.**

## Objetivo y brecha anterior

El laboratorio 0029 probó autenticación antes del drenaje, pero `app.jellyfin_hls` sigue emitiendo capacidades HLS v1 transferibles entre perfiles autenticados, con validez máxima de cuatro horas. Una protección aplicada únicamente a `playback-info` no corta playlists, segmentos, claves ni reintentos `Range`.

Este hito desarrolla un contrato v2 y una autoridad SQLite privada que vinculan cada URL a **medio exacto + perfil activo + cookie JWT de un login concreto + sesión HLS persistente + generación revocable + raíz del vídeo en Jellyfin**. El hito **NO activa esa barrera en producción** ni aporta por sí solo autorización de borrado.

## Implementación en la rama

1. `backend/app/auth.py`: cada token nuevo de login incorpora `jti` aleatorio de 128 bits; así, incluso dos logins del mismo perfil dentro del mismo segundo tienen JWT distintos. El control habitual de sesiones permanece; el módulo HLS v2 requiere además `jti` válido. Los JWT anteriores sin `jti` siguen siendo aceptables para la autenticación existente, **pero no para emitir capacidades v2**.
2. `backend/app/retirement_hls_capability_lab_0031.py`: formato firmado v2 obligatorio con campos cerrados y tipos exactos; HMAC-SHA256 separado por dominio; comparación en tiempo constante; huella HMAC de cookie autenticada sin publicar el cookie; denegación de firmas, campos duplicados/adicionales, versiones v1, caducidad, perfiles, logins, medio, sesión, generación y rutas no canónicas. Cada ruta permanece bajo la misma raíz `/videos/{id}/`. Emite variantes, segmentos, `URI` de claves y playlists reescritas con el MISMO contexto. No accede por red a Jellyfin.
3. `worker/retirement_hls_session_lab_0031.py`: extensión de 0029 limitada al directorio TEMP de 0027, SQLite privada con permisos estrictos, `BEGIN IMMEDIATE` y `synchronous=FULL`. Abre una sesión de perfil/cookie/generación de forma atómica; al admitir cada GET comprueba estado, generación, sesión, dueño y raíz **en la misma transacción en la que reserva una lectura**. Drenaje aumenta la generación una única vez, rechaza nuevos segmentos, conserva las lecturas ya iniciadas y no recupera sesiones tras un crash por caducidad ficticia. La desconexión/terminación de cada respuesta debe cerrar su reserva.
4. `backend/tests/test_hls_capability_0031.py`: FastAPI TestClient sobre rutas ficticias; usa `get_current_profile` auténtico, cookies JWT genuinas, base de perfiles en memoria, origen Jellyfin ficticio y SQLite TEMP con marcador de laboratorio. Prueba master, `URI` de clave, fragmentos, petición `Range`, reaprovechamiento entre perfiles/logins, revocación, edición de firma, duplicados, versión antigua, otra raíz, otra película, cierre de sesión y reapertura de la SQLite simulando una interrupción. **No se ha matado un proceso real durante este hito 0031**.

**Limitación explícita:** los módulos 0031 NO se importan desde `app.main`, y `jellyfin_playback.py` productivo sigue usando HLS v1 hasta que exista un cambio de todas las rutas, con estado durable en la DB real, un protocolo de cierre de sesiones de cliente y pruebas en dispositivos. Nunca desplegar un modo mixto en el que v1 pueda saltarse la revocación.

## Descubrimiento importante del aislamiento — inventario real read-only

- Hay un **Jellyfin nativo Windows** (`jellyfin.exe`) escuchando en **0.0.0.0:8096** y un **Jellyfin Docker** `viewtv-jellyfin` publicado únicamente en **127.0.0.1:8097**. El primero está asociado a un proceso distinto, no al contenedor Docker. Un binding en todas las interfaces **no prueba** acceso desde la LAN sin revisar cortafuegos, rutas de red y medios montados; tampoco prueba que ambos servidores accedan a las mismas películas. Debe demostrarse o excluirse antes de permitir retiradas.
- El contenedor `viewtv-jellyfin` monta `/media/Peliculas` y `/media/Series` como **solo lectura**. Esto no impide que mantenga handles abiertos de reproducción.
- Windows también muestra qBittorrent nativo con escucha en **[::]:8080**. Queda pendiente validar qué interfaces/redes llegan a su Web UI y cómo impedir una reanudación durante una custodia de descarga, sin modificar torrents actuales.
- Se usaron `Get-NetTCPConnection`, `Get-Process` y `docker ps/inspect` solo para lectura. No se tocaron reglas de firewall, puertos, ACL, procesos, rutas NTFS, caché Jellyfin, torrents, sesiones de usuario ni contenedores.

## Pruebas, recuperación y límites

- Tests de HLS existentes, 0029 y nuevo laboratorio 0031: **54/54 PASS**, una advertencia de dependencia externa. El smoke read-only real **10/10 PASS**. TypeScript y ESLint pasan.
- Ruff de **los cuatro ficheros cambiados**: **PASS**. La reserva anterior **Ruff global 128 incidencias** en ficheros históricos ajenos a 0031 aún debe resolverse por separado, sin ocultarla ni desactivar reglas. Sin Ruff global verde no se considera cerrada la puerta de calidad para despliegue de nuevos mecanismos.
- Suite completa del backend: **1547/1547 PASS**, dos advertencias externas (Starlette/FastAPI); Docker de pruebas aislado sin red, fuentes montadas solo lectura. No confundir el éxito de tests con un despliegue.
- No hay mecanismo de borrado en este hito; ninguna película real puede alcanzar permiso de retirada por esta vía. Hitos 3/4/5 bloqueados; **4/4 películas siguen bloqueadas** en el preflight real read-only repetido tras 0031: 2/2 diarios NTFS verificados, permiso físico NO, 0 archivos borrados y 0 torrents modificados.

## Próxima transición segura

**Terminar hito 2 en la integración real, todavía sin despliegue:** incorporar persistencia de sesión/generación y autenticación por cookie a `playback-info`, streaming directo y cada GET HLS; registrar el fin de cuerpo HTTP/abortos, probar condiciones de carrera reales, revocación duradera y reproducción en navegador/TV. Evitar tokens v1 transferibles incluso durante migraciones.

**Hito 3:** investigar específicamente Jellyfin nativo 8096 frente a Docker 8097 y el servicio qBittorrent 8080, redes/ACL/interfaces, handles NTFS y custodia por descarga. Ningún bloqueo de HLS sustituye a estas pruebas. No detener torrents, ni borrar películas, ni cambiar Jellyfin sin barrera completa, autorización administrativa real por película y respaldo/rollback validado.

**Hitos 4/5:** requieren alta de administrador independiente, aprobación concreta por película, diario Windows duradero y ejecutor con restauración/medición de bytes físicos. Mantener todas las negativas por defecto y PR #2 sin fusionar.
