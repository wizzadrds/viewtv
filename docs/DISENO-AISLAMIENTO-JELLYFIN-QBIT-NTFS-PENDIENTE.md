# Diseño pendiente — cerrar accesos Jellyfin, escrituras qBittorrent y lectores NTFS (futuro hito 3)

**Estado: DISEÑO Y MATRIZ DE PRUEBAS; NO IMPLEMENTADO NI DESPLEGADO.** El 0032 ha añadido evidencia de red y firewall de Windows de solo lectura, descrita en [AVANCE-HLS-RUTAS-REALES-AISLAMIENTO-0032-20261127.md](AVANCE-HLS-RUTAS-REALES-AISLAMIENTO-0032-20261127.md): Jellyfin nativo escuchando en `0.0.0.0:8096` con reglas `Allow` en Private/Public (TCP/UDP, puertos y origen `Any`), Jellyfin Docker en `127.0.0.1:8097`, y qBittorrent nativo `[::]:8080` también con reglas de entrada `Allow` Private/Public. No se ha probado aún acceso LAN efectivo ni si Jellyfin nativo comparte película concreta; no cambiar reglas sin valorar clientes. No se pausa ni detiene ningún torrent. El mutex productivo del 0030 solo cubre procesos que lo adquieren: el publicador sí, Jellyfin, qBittorrent y otros lectores no.

## Principio

Una retirada debe tener una barrera única de admisión y un procedimiento de drenaje bajo identidad de **descarga exacta + medio exacto + ID de archivo NTFS**. No basta contar sesiones Jellyfin ni confiar en `HTTP 200`, y el cierre de API no impide accesos directos al puerto Jellyfin, a la GUI qBittorrent o a otro lector de disco. Todas las fuentes deben demostrar quietud, no asumirla; cualquier fallo conserva todas las películas.

## Tres vías que cerrar

**Acceso directo Jellyfin:** inventariar bindings Docker/Windows, puertos IPv4/IPv6, LAN, publicación externa, URL directa, proxy, clientes con API key y sesiones ya abiertas. Restringir de verdad la entrada mediante red/ACL/reglas de host comprobadas desde clientes externos, sin romper los dispositivos de reproducción autorizados. El control de perfil y generación del hito 2 es obligatorio antes de autorizar drenaje. Revalidar sesiones y descargas de contenidos activos bajo la misma barrera, incluidos streams iniciados antes del cambio.

**Escrituras de qBittorrent:** el mutex Windows no lo bloquea. Inventariar hash e identidad del torrent, ficheros y metadatos extras (los **4 extras de 488 bytes lógicos quedan intocables**), estado y procesos. Diseñar una transición transaccional de custodia por descarga, con prueba de que no hay escrituras ni handles y de que no puede reanudarse silenciosamente. Pausar/detener **solo el torrent de la única película autorizada en el futuro hito 5**, nunca ahora; un estado `stopped` leído antes no demuestra quietud posterior. Cerrar interfaces de reanudación no autorizadas durante la operación; usar evidencia del cliente y del volumen.

**Lectores NTFS:** impedir nuevas aperturas desde cualquier ruta/hardlink, no solo desde VIEWTV; inventariar identidad por volumen e índice (File ID), ACL, reparse/junctions, hardlinks, procesos y handles abiertos. Probar apertura exclusiva o mecanismo equivalente con evidencia de kernel y asegurar bloqueo hasta completar o revertir. No cambiar ACL de los originales NTFS compartidos ni caché Jellyfin en esta fase. Si no puede aislarse un lector externo, bloqueo cerrado.

## Puerta conjunta de retirada (futura, no activa)

Transición durable `libre → cerrando admisión → drenando → quiescente verificable → autorización por película → retirada controlada`; un reinicio o pérdida de observabilidad devuelve el estado a `bloqueada/revisión`, nunca a permiso por defecto. Revalidar identidad NTFS y diarios 2/2, petición concreta, aprobación HMAC 0019 consumible una vez, 4/4 vistas requeridas, espacio, perfiles y los tres canales. La carpeta sin diario queda excluida.

## Pruebas exigidas antes de dar cobertura

- Cliente directo a Jellyfin desde LAN/host/IPv6/proxy durante drenaje: **denegado**; cualquier puerto alternativo en pie invalida la barrera.
- Sesión Jellyfin abierta antes del drenaje y stream que tarda en finalizar: debe mantenerse bloqueo hasta cerrar cuerpo de respuesta y handles.
- qBittorrent escribe, reanuda manualmente o tras reinicio durante custodia: operación de retirada no progresa; validar por proceso y trazas de fichero, no solo estado API.
- Otro proceso abre por hardlink/original/alias, un descriptor permanece abierto o hay junction/reparse: bloquear sin borrar; probar también carreras entre comprobación y apertura.
- Interrupción del proceso guardián/reinicio Windows-Docker/fallo de red e incoherencia de journals: bloqueo duradero.
- Verificación de exclusiones: cuatro metadatos qBit intocados, carpeta sin diario excluida, ningún acceso a caché Jellyfin ni originales.
- Una revisión futura de red y operaciones deberá demostrar **desde dispositivo** que la reproducción habitual sigue funcionando.

**Fuera de cobertura hoy:** redes alternativas y clientes directos Jellyfin; qBittorrent que no comparte mutex; lectores y handles NTFS externos; tokens HLS actuales transferibles. **No ejecutar retirada** aunque el publicador 0030 ya esté actualizado.
