# VIEWTV 0038 — custodia durable por descarga y parada exacta, exclusivamente laboratorio

**Fecha:** 28/11/2026. Rama `viewtv-seguimiento-descargas-0012`, PR #2 OPEN/DRAFT; **no fusionar ni desplegar**. Alcance: método genérico en cliente qBittorrent, autoridad SQLite privada y pruebas sin red y solo con `httpx.MockTransport`. **No se ha enviado ninguna orden `stop` al qBittorrent del equipo.**

## Finalidad

El hito 0026 verificaba en solo lectura la correlación entre el diario de publicación, hash, etiqueta `viewtv-descarga-N`, raíz de descarga, estados de qBittorrent y todos sus archivos (incluidos los extras). Dos capturas consistentes **no impiden** que qBittorrent se reactive después. En 0038 se crea el tramo de protocolo para detener **un único hash** de forma idempotente frente a caídas, sin sugerir que ello basta para autorizar borrar archivos.

## Cambios de código

1. `backend/app/qbittorrent.py` incorpora `stop_torrent(hash)`, que valida **solo un hash SHA1 de 40 o SHA256 de 64 hexadecimales**, y realiza exclusivamente `POST /api/v2/torrents/stop` con `hashes=<un-hash>`. Rechaza `all`, separadores `|`, listas, cadenas vacías y entradas extrañas **antes de cualquier HTTP**. La operación está disponible como método, pero ninguna ruta productiva de VIEWTV la invoca. La ruta está documentada por la API oficial de qBittorrent 5.x.
2. `worker/retirement_qbit_stop_lab_0038.py`: **un constructor que exige `httpx.MockTransport`** para que el laboratorio no tenga una conexión real, y un directorio TEMP con nombre y marcador del ensayo 0027, dueño actual y permisos `0700`. El diario privado SQLite exige `0600`, archivo regular y un solo enlace, `synchronous=FULL`, `journal_mode=DELETE`, `BEGIN IMMEDIATE`; toda mutación del estado queda persistida con `COMMIT`.
3. `registrar()` exige identidad del medio, descarga exacta, solicitud TMDB, diario de publicación, hash, etiqueta, ruta, progreso, lista íntegra de archivos y tamaños coincidentes. Conserva como huella SHA256 la **lista completa**, incluidos metadatos extras. Solo permite **una custodia por sandbox**, con estado inicial `registrada`.
4. `ordenar_stop()` realiza GETs exactos solo para ese hash y comprueba la huella, antes de guardar durablemente `orden_pendiente`. **Solo después** manda `stop_torrent(hash)` al mock. Si el mock informa que ya está detenido, no envía un POST innecesario. Tras confirmar devuelve estado `orden_enviada`. Si el proceso cae durante la llamada o se pierde respuesta, el estado `orden_pendiente` queda en disco y **no permite reenviar** automáticamente.
5. `observar()` reconsulta estado, hash, ficheros y huella en dos lecturas. Si ha variado la ruta, identidad, progreso, archivo auxiliar o se ha reanudado el torrent, queda `bloqueada` de forma durable. Puede registrar `parada_observada`, **pero esto nunca es quietud kernel ni permiso de borrado**: una GUI, otro token WebUI, otro proceso o reinicio todavía pueden reanudar/escribir.

## Tests de seguridad

`backend/tests/test_qbit_stop_lab_0038.py`: **43 pruebas nuevas** de hash único/40+64, ausencia de `all`, listas y múltiples hashes; única orden `stop`, otros torrents intactos, estado inicialmente parado sin POST, metadatos extras de 488 bytes preservados, alteraciones de nombres/tamaños/prioridad/identidad, campos malformados, ausencia de transporte de red, SQLite sin permisos privados, reanudación entre lecturas, dos hilos concurrentes emitiendo como máximo un POST y rehidratación tras respuesta HTTP perdida.

Además, una prueba **mata de verdad un proceso hijo con `os._exit(77)` justo después de recibir el `POST` en un MockTransport**. Tras abrir nuevamente la misma base SQLite se observa `orden_pendiente`; no se reenvía la orden y solo se registra una observación posterior. Es una prueba de interrupción del proceso de laboratorio, **no una caída de Windows/qBit productivos**.

Verificaciones dirigidas: **134/134 PASS** para qBit + custodia + pruebas nuevas; hito 0038 **43/43 PASS**, Ruff global `backend worker scripts` PASS. **Regresión completa final:** backend **1644/1644 PASS** en Docker sin red con código montado read-only (2 advertencias externas Starlette/FastAPI); TypeScript PASS, ESLint PASS, Ruff global backend/worker/scripts PASS y smoke HTTP real de solo lectura **10/10 PASS**. Directorio y base del laboratorio TEMP con permisos privados verificados; copia privada del cliente original fuera de la rama en `/home/viewtv/viewtv-backups/0038-20261128/qbittorrent.py.original`, SHA256 `61be7bac88c228c688fd85bc956089981843186937b2da65251e79c544062098`. No se ha alterado el qBittorrent productivo.

## Observación real read-only posterior

El orquestador 0026 ha ejecutado dos consultas SQL/Jellyfin/qBittorrent y diarios/NTFS coincidentes. **Hay 2 descargas, ninguna con torrent completo y en reposo declarado (2/2 no en reposo o incompletos); los 6 archivos qBit incluyen 2 publicados y 4 extras protegidos (488 bytes lógicos).** No se ha detenido ningún torrent. El preflight real 0018 encuentra **4/4 películas bloqueadas**, 2/2 diarios NTFS verificados, ninguna autorización administrativa de retiro, 0 ficheros eliminados y 0 torrents modificados. Smoke real read-only: **10/10 PASS**.

## Barreras que faltan para el funcionamiento productivo

Este laboratorio es un paso de protocolo, **no una custodia transaccional de qBittorrent real**: no controla una reanudación externa simultánea a los dos GETs, un reinicio del torrent, el servicio, la GUI u otros clientes API; la detención de qBit por sí sola no bloquea handles NTFS ni la creación de terceros hardlinks. Ningún `stop` real fue autorizado o enviado y no debe usarse uno para convertir artificialmente una película no apta en apta. Tampoco existen enrolamiento productivo del broker Windows, ACL de la película exacta, HLS v2 desplegado sin bypass, protección de Jellyfin directo, autorización admin por película, ejecutor/diario de retiro físico ni prueba de bytes liberados en producción.

Antes de integrar el POST real se necesita: consentimiento específico sobre **una película/torrent apto** y una ventana de mantenimiento, identidad Windows propia del broker, mecanismo que bloquee escrituras/reanudación mientras permanezca la transacción, prueba de handles/sesiones y un protocolo de recuperación de servicios/reinicio sin reemitir órdenes erróneas. **Todos los resultados de 0038 siguen expresando `autoriza_borrado_fisico=False`.**

La prioridad continúa siendo acabar el borrado seguro antes de Samsung y Momentos.
