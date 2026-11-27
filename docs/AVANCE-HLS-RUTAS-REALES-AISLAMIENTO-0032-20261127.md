# VIEWTV 0032 — HLS v2 en rutas FastAPI reales bajo laboratorio y auditoría de vías externas

**Fecha:** 27/11/2026 (Madrid). **Rama autorizada:** `viewtv-seguimiento-descargas-0012`; PR #2 abierta y draft, **nunca fusionar**. **Tipo:** avance en código + TestClient sobre las rutas reales, con datos enteramente ficticios; inventario de Windows real exclusivamente de lectura. **Sin despliegue, sin borrados ni paradas.**

## Objetivo: acercar la barrera 0031 al circuito real de reproducción

El 0031 creó la autoridad HLS v2 (perfil, cookie autenticada con jti, sesión durable, generación revocable, raíz exacta de vídeo). No se usaba todavía en los endpoints `/jellyfin/media/{id}/playback-info` ni `/jellyfin/media/{id}/hls` de la API.

En 0032 se añadió una dependencia de FastAPI `get_hls_bridge_0032` que **devuelve `None` por defecto**: la API productiva no registra una autoridad y mantiene su HLS v1 mientras se diseña una migración segura. Solo un test, sobre `app.main.app` **en memoria**, inyecta `HLSRouteBridgeLab0032` con un banco de datos de perfiles ficticios y una SQLite TEMP GUID con marcador y permisos `0700/0600`. Esto prueba el **código de handlers reales**, no endpoints reinventados; la integración está ausente del servicio desplegado.

En el modo inyectado de laboratorio:
- `playback-info` crea una sesión HLS 0031 y emite una capacidad v2 en lugar del enlace v1, asociada a perfil, login, película, generación y raíz del vídeo.
- Cada `GET /hls` primero autentica el perfil, comprueba criptográficamente la capacidad, su dueño y generación, y **reserva la lectura en la misma transacción SQLite que comprueba drenaje**, antes de abrir el origen Jellyfin ficticio.
- Las listas master, las URI de claves y los segmentos se reescriben manteniendo la misma sesión/generación; los reintentos `Range` también pasan por el guard. La lectura de playlist se libera al terminar y la de vídeo solo en el `finally` del iterador HTTP; también se libera si falla la apertura del upstream.
- El wrapper ASGI autenticado 0029 se instala **únicamente en el TestClient** y realiza admisión para negociación, streaming directo y HLS. Solo **después** de autenticar y reservar en SQLite, marca la petición ASGI; el puente estricto exige esa marca para cualquiera de las tres rutas, denegando sin contactar con Jellyfin si falta el wrapper. Un usuario anónimo recibe 401 antes de observar el estado de drenaje. HLS v1 no pasa la verificación v2 cuando está inyectado el puente de pruebas.
- Un segmento retenido artificialmente en un hilo conserva la reserva hasta terminar su cuerpo; iniciar drenaje impide nuevas lecturas y no declara quietud hasta terminar el stream y cerrar la sesión.

**Límite crítico:** no basta con instalar el puente sin la barrera ASGI 0029. `get_hls_bridge_0032=None` mantiene por compatibilidad el comportamiento legacy, de modo que **HLS v1 continúa transferible en el despliegue real**. La sesión HLS del laboratorio requiere cierre explícito, y faltan protocolo real de parada/abandono, persistencia productiva, recuperación tras reinicio, validación en navegador/TV y migración sin ventana de bypass. Una sesión que no se cierra bloquea la retirada: comportamiento fail-closed, todavía no operación madura.

## Auditoría Windows real de vías alternativas: indicio concreto de riesgo

Se ha inspeccionado exclusivamente con consultas de Windows/WSL/Docker, sin modificar reglas ni leer películas:
- Jellyfin nativo Windows: proceso `jellyfin.exe` escuchando en IPv4 **`0.0.0.0:8096`**. El Jellyfin Docker `viewtv-jellyfin` está publicado en **`127.0.0.1:8097`** y monta `/media/Peliculas` y `/media/Series` en modo solo lectura. Son **dos procesos distintos**; no se presupone qué bibliotecas comparte el nativo.
- qBittorrent Windows: proceso `qbittorrent.exe` con escucha en **`[::]:8080`**. No se han consultado credenciales ni modificado su configuración.
- En `ActiveStore` hay **reglas de entrada `Allow` habilitadas por aplicación** para `Jellyfin.Server` en perfiles `Private, Public`, protocolos TCP/UDP, `LocalPort=Any`, `RemoteAddress=Any`. También hay reglas qBittorrent `Allow` para `Public` y `Private`, TCP/UDP, `LocalPort=Any`, `RemoteAddress=Any`.
- Estas reglas y listeners **no demuestran accesibilidad efectiva desde cada cliente o segmento LAN** (faltan prueba externa de red, políticas superpuestas y observación de rutas al medio), pero impiden afirmar que el tráfico directo esté cerrado. Un mutex local o la barrera HLS de ViewTV NO controlan estos otros procesos.

**No cambiar automáticamente estas reglas:** podrían ser necesarias para reproducción y torrentes. Antes de un plan de cierre, identificar qué clientes autorizados dependen de cada vía, si Jellyfin nativo usa los mismos NTFS y cómo conservar la reproducción con el mínimo acceso necesario. Los cuatro archivos auxiliares de qBit permanecen bajo custodia.

## Cambios auditables y pruebas

- `backend/app/retirement_hls_bridge_contract_0032.py`: contrato de inyección y denegación; por defecto ninguna autoridad productiva.
- `backend/app/retirement_hls_route_bridge_lab_0032.py`: adaptador para emitir, reservar, reescribir, finalizar lecturas y cerrar sesiones HLS exclusivamente en SQLite TEMP 0031.
- `backend/app/jellyfin_playback.py`: puntos de extensión en **los handlers reales** de negociación, streaming directo y HLS, con comprobación obligatoria de admisión al inyectar el puente; conserva compatibilidad por defecto, sin registrar el adaptador.
- `backend/app/retirement_authenticated_gate_lab_0029.py`: marca de admisión ASGI solo tras validar perfil y reservar petición; ningún header del cliente puede crearla.
- `backend/tests/test_hls_real_routes_lab_0032.py`: perfiles/JWT genuinos pero ficticios, Jellyfin mock, cookies distintas, v1 rechazado en modo lab, no filtrado previo a autenticación, master/URI clave/segmento/Range, drenaje de las tres rutas, fallos upstream/playlist y stream concurrente que mantiene la barrera.

**Verificaciones comprobadas antes del commit:** Ruff de los ficheros modificados aprobado; **8/8 pruebas nuevas dirigidas PASAN**, incluida la denegación de las tres rutas cuando el puente está inyectado pero no existe admisión ASGI. Se corrigió el fixture de respuesta HTTP bloqueante tras detectar un API mock incompatible; no hubo fallos de producto ni permisos reales. **Backend íntegro 1555/1555 PASS** (dos advertencias de dependencias Starlette/FastAPI), en Docker sin red y con código montado en modo solo lectura. **TypeScript PASS**, **ESLint PASS** y **smoke HTTP real solo lectura 10/10 PASS**. Todos los tests nuevos del 0032 y las regresiones 0029/HLS dirigidas **43/43 PASS** después del endurecimiento de la marca ASGI. Ninguno de estos tests sustituye el despliegue o prueba del dispositivo. Ruff de todo el repositorio conserva 128 incidencias heredadas y **no se declara verde**. No se han alterado ni desactivado reglas globales; un capturador explícito de fallos del hilo ficticio lleva un `noqa: BLE001` local y justificado en el test, no en el producto. Respaldo privado de `jellyfin_playback.py` y `BACKLOG.md` creado antes del cambio en `/home/viewtv/viewtv-backups/0032-20261127`, con hash verificado del primero; el original del gate 0029 se ha recuperado además desde HEAD en ese directorio. Ningún respaldo privado se sube a Git.

**Read-only NTFS posterior:** preflight 0018 muestra `PELICULAS_ANALIZADAS=4`, `DIARIOS_NTFS_VERIFICADOS=2`, `DIARIOS_VERIFICADOS_EN_SNAPSHOT=2`, `PELICULAS_BLOQUEADAS=4`, `PERMISO_DE_BORRADO_OTORGADO=NO`, `ARCHIVOS_ELIMINADOS=0`, `TORRENTS_MODIFICADOS=0`. Persisten 4 autorizaciones admin ausentes, perfiles sin marcar vista, dos torrents activos/incompletos y dos inventarios incompletos/no verificables.

## Siguiente paso efectivo hacia la retirada segura

1. Terminar **hito 2**: registrar bajo control de autenticación la barrera única de rutas reales, dar persistencia al estado de sesión HLS y directo, detener/reanudar clientes con protocolo explícito, gestionar respuesta abortada, generar/revocar sesiones en todos los métodos y cerrar definitivamente HLS v1, con pruebas en navegador y TV; no desplegar una migración que acepte a la vez una vía insegura.
2. **Hito 3**: resolver los listeners/rules nativos de Jellyfin y qBittorrent de forma compatible con uso legítimo; verificar acceso LAN desde clientes permitidos, aislar los procesos de escritura, demostrar handles NTFS y reserva por descarga idéntica en el kernel. Fallo o duda = impedir retirada, sin detener torrent ni cambiar firewall.
3. **Hito 4/5**: alta de administrador independiente, autorización de una película concreta, journal con recuperación y ejecutor de unlink de enlaces exactos bajo reserva, medición de bloques/liberación real y rollback. **Ni un solo borrado hasta existir una candidata realmente autorizada y verificable.**

**PR #2 sigue abierta y en borrador; no fusionar. La prioridad sigue siendo concluir espacio/borrado seguro; Samsung y Momentos permanecen pospuestos.**
