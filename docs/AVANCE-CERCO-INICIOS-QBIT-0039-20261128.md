# VIEWTV 0039 — cerco SQLite del trabajador de inicio frente a custodia de retirada

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`, PR #2 abierta/draft y sin fusionar. **Estado:** laboratorio sintético, NO desplegado, sin parada/reanudación real de torrent y sin borrar medios.

## Motivación

La custodia 0038 registra de forma durable la intención `stop` de un hash qBittorrent único, con `BEGIN IMMEDIATE` y recuperación sin repetir el POST tras caída. Pero el proceso `worker/download_starter.py` de VIEWTV ya puede iniciar individualmente torrents pendientes con `start_torrent()`: sin una barrera compartida, podría reanudarse la misma descarga en una carrera con el futuro proceso de retirada. Además, qBittorrent dispone de WebUI, GUI y otras interfaces independientes del worker. Dos lecturas del estado qBit no prueban exclusión.

## Qué incorpora 0039

- `worker/retirement_qbit_start_fence_lab_0039.py`: adaptador `InicioCustodiadoLab0039` que implementa `torrents_info` y `start_torrent` para poder ser inyectado **sin modificar** el trabajador real `worker/download_starter.process_one_start`. Exige la custodia 0038 en la carpeta TEMP privada marcada y una instancia `QBittorrentClient` con `httpx.MockTransport`; no acepta conexiones de producción.
- Un `start_torrent(hash)` simulado comienza **`BEGIN IMMEDIATE` sobre la MISMA SQLite** que `CustodiaQbitLab0038.registrar` y su `ordenar_stop`, valida que no exista registro de custodia para el hash (en **cualquier** estado: `registrada`, `orden_pendiente`, `orden_enviada`, `parada_observada` o `bloqueada`) y mantiene abierta la transacción hasta finalizar el `POST /api/v2/torrents/start` **al mock**.
- Si el START estaba en vuelo **antes** de que se solicite la custodia, el registro de retirada espera a que termine el POST simulado; después se establece el cerco y nuevos START del hash se rechazan. Si el registro llegó antes, el START no se envía. No caduca automáticamente; tras reabrir SQLite sigue rechazando arranques del mismo hash. No bloquea los hashes de otras descargas.
- Se preserva el contrato de denegación: una SQLite corrupta, privilegios/permisos inválidos, un hash `all`/lista/malformado o un `MockTransport` cambiado por transporte real abortan, sin permiso físico de borrado. **El módulo no está importado por la API ni por los servicios activos.**

## Pruebas

`backend/tests/test_qbit_start_fence_lab_0039.py`: **25 casos nuevos** con SQLite privada ficticia; estados de custodia, rehidratación tras reinicio, hash ajeno, datos malformados, pérdida de privacidad de SQLite y simulación de corrupción. Dos tests de concurrencia usan múltiples hilos: el alta de custodia espera al START que ya adquirió la transacción y múltiples peticiones de START posteriores a la custodia son rechazadas. El test de integración ejecuta **el verdadero `worker/download_starter.process_one_start`** sobre SQLModel SQLite de ensayo: el torrent bajo custodia queda pendiente sin POST, y otro torrent sin custodia conserva su inicio individual.

Una prueba negativa imprescindible usa **el cliente qBit simulado por fuera del adaptador** para reenviar START mientras el ledger dice `parada_observada`: la operación se puede hacer desde esa otra interfaz y el ledger 0038 detecta la reanudación después, pasando a `bloqueada`. El test prueba expresamente que el cerco de VIEWTV **NO es una exclusión kernel ni un cierre de la GUI/WebUI de qBittorrent**, por lo que no se puede autorizar ningún unlink.

**Calidad verificada:** Ruff de los ficheros nuevos y Ruff global `backend worker scripts` PASS; **25/25 tests 0039 PASS**; **backend íntegro 1669/1669 PASS**, en Docker sin red con código readonly (dos advertencias de deprecación externas Starlette/FastAPI); **TypeScript PASS**, **ESLint PASS** y **smoke HTTP real en solo lectura 10/10 PASS**. `git diff --check` PASS. Se prueba también que la lectura qBit del adaptador falla cerrada si se sustituye `MockTransport` por transporte real después del constructor.

## Inventario real read-only de seguridad

Auditoría qBit/diarios 0026: dos descargas, **0/2 torrents en reposo completo reportado**, dos publicados y cuatro archivos extra intocables de **488 bytes lógicos**. El preflight 0018 sigue con 4/4 películas bloqueadas, 2/2 diarios NTFS verificados, 0 películas eliminadas, 0 torrents modificados y permiso físico NO. Ningún código del hito 0039 emitió HTTP a qBittorrent real; toda red nueva se limita a `MockTransport` dentro de Docker `--network none`.

## Qué falta para producción

1. **Habilitar una única autoridad de inicio y parada en producción**, compartiendo una transacción/fencing token y protegiendo el endpoint/credenciales qBit contra accesos alternativos. Mientras GUI/WebUI, reinicio del cliente o un proceso ajeno puedan enviar START, un fence SQLite solo del worker no asegura quietud.
2. La identidad Windows segregada del broker (0037) debe controlar el File ID concreto con DACL que impida nuevos hardlinks; los handles antiguos deben estar drenados y comprobarse tras suspender **una descarga apta y autorizada**, no las descargas actuales. Integrar los dos diarios NTFS, no alterar archivos extra ni toda la biblioteca.
3. Cerrar HLS v1 y el acceso directo a Jellyfin manteniendo los clientes legítimos; instalar guard HLS v2 duradero y comprobar abortos/cierres. Administración independiente, aprobación firmada/consumida por película y ejecutor Windows durable con recuperación real y medición de espacio físico.
4. La primera ejecución real requiere **una película específica que cumpla todas las condiciones y autorización expresa**. Las cuatro siguen bloqueadas. No fusionar ni desplegar PR #2 mientras falten barreras.

**Conclusión:** 0039 demuestra la serialización del inicio VIEWTV con la custodia 0038 bajo un adaptador ficticio. **La protección productiva de reanudaciones externas no está terminada.**
