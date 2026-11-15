# Estado de VIEWTV y continuación del desarrollo

**Fecha de corte:** 15 de noviembre de 2026  
**Rama de trabajo:** `inventario-trabajo-local`  
**Estado:** pausa voluntaria tras completar la implementación y validación local del bloque de solicitudes, búsqueda y selección manual. El circuito real de descarga todavía no está validado de extremo a extremo.

> Esta nota documenta el estado observado en el entorno local WSL/Docker. Su publicación no implica que los cambios de código recientes estén ya confirmados o sincronizados en GitHub. No se ha cambiado de rama, no se ha hecho push a `main`, ni se ha enviado ningún torrent real a qBittorrent.

## 1. Resumen ejecutivo

VIEWTV ya puede crear solicitudes manuales de películas/series, procesarlas en un worker, consultar Jackett mediante Torznab XML, guardar los resultados y ofrecer una selección manual al perfil propietario. Los títulos de los resultados se enriquecen con metadatos técnicos inferidos del nombre (resolución, calidad, fuente, códec e idioma) y se ordenan priorizando 4K y después 1080p, 720p, 576p y 480p.

La selección del usuario crea una fila durable `Descarga`, pero el endpoint de selección **no envía el torrent a qBittorrent**. El worker separado dispone de un procesador que consume esa selección, reconcilia por etiqueta en qBittorrent y puede enviar el magnet/enlace privado después de la selección explícita. Esa última parte está implementada y tiene pruebas unitarias, pero aún no se ha probado con una transferencia real.

## 2. Trabajo implementado y validado localmente

### Solicitudes

- Solicitudes desde un elemento del catálogo Jellyfin y solicitudes manuales por título, tipo (`pelicula`/`serie`) y año opcional.
- Las solicitudes manuales no requieren un ID de Jellyfin.
- Deducción de duplicados activos por perfil; la comparación de títulos manuales ignora diferencias de mayúsculas y espacios exteriores.
- Los estados fallidos permiten crear un nuevo intento.
- Las consultas y acciones están limitadas al perfil autenticado.
- La solicitud manual se procesa sin exigir que el archivo exista previamente en Jellyfin.

### Búsqueda Jackett

- Adaptador genérico Torznab con lectura de XML; no se parsea HTML ni se automatizan páginas web.
- El worker traduce el tipo de medio a búsqueda de película o TV, incorpora el año cuando está disponible y guarda los resultados normalizados.
- Se conservan versiones distintas cuando tienen hashes/enlaces diferentes; se descartan duplicados técnicos y resultados no utilizables.
- Al finalizar la búsqueda, la solicitud pasa a `esperando_seleccion` y libera su lease mientras espera la decisión del usuario.
- Los resultados son privados para el perfil propietario.
- El endpoint de resultados no devuelve enlaces de descarga, magnets, hashes ni claves API.

### Metadatos y selección manual

- Añadido `backend/app/metadatos_resultado.py` para extraer:
  - resolución: 2160p, 1080p, 720p, 576p y 480p;
  - etiqueta de calidad: 4K, Full HD, HD o SD;
  - fuente: BluRay, BDRip, BRRip, WEB-DL, WEBRip, HDRip, DVDRip o HDTV;
  - códec: HEVC, H.264 o AV1;
  - idioma declarado: español, latino, dual/multi o VO/subtitulada.
- Los valores no detectados se dejan como desconocidos; no se presentan como hechos verificados.
- La API ordena por resolución y, dentro de ella, seeders descendentes y título.
- El usuario selecciona manualmente una versión. No hay selección automática ni envío automático al elegir.
- El endpoint de selección verifica perfil, solicitud y pertenencia del resultado; crea `Descarga` de forma transaccional y evita selecciones duplicadas.

### Cola y worker de descargas

- `Descarga` dispone de intentos, máximo de intentos, disponibilidad diferida, lease, propietario, vencimiento y heartbeat.
- El worker reclama descargas seleccionadas, busca primero una transferencia existente mediante una etiqueta única, y solo después intenta añadir el torrent.
- La reconciliación por etiqueta reduce el riesgo de duplicar una transferencia si qBittorrent aceptó una petición pero se perdió la respuesta.
- Se registran hash de qBittorrent, reintentos y errores; los fallos terminales permiten volver a la solicitud para una nueva selección.
- El worker se ejecuta como servicio independiente de la API y consulta la cola periódicamente.
- El estado heredado `vigilando` se conserva por compatibilidad; no se le ha añadido comportamiento de vigilancia automática.

### qBittorrent y despliegue

- qBittorrent está instalado de forma nativa en Windows; API y worker corren en Docker/WSL.
- Versión comprobada: qBittorrent v5.3.0.
- La conectividad desde el contenedor worker y la autenticación Bearer se probaron correctamente.
- El cliente implementa consulta de torrents por hash/etiqueta y envío de torrent mediante API.
- API y worker comparten el volumen SQLite persistente; ambos se construyen con el Dockerfile del proyecto.
- La API quedó healthy, el worker arrancado y los endpoints de solicitudes/resultados/selección aparecieron en OpenAPI.
- La migración `0008_solicitud_jellyfin_nullable` se aplicó a la base activa tras crear una copia previa. La columna `jellyfin_item_id` permite ahora `NULL` para solicitudes manuales.

## 3. Pruebas y comprobaciones

Última validación local comunicada el 15 de noviembre de 2026:

- `pytest -q`: **129 passed**.
- `ruff check app tests ../worker`: **All checks passed!**
- La suite incluye pruebas para solicitudes manuales, aislamiento por perfil, resultados privados, selección sin envío, metadatos técnicos, orden de calidades, worker de búsqueda, worker de descargas, leases, reintentos y reconciliación simulada de qBittorrent.
- Quedaron dos advertencias de dependencias/deprecación en la suite: integración Starlette TestClient/httpx y el alias `HTTP_422_UNPROCESSABLE_ENTITY`. No bloquearon las pruebas.

La conectividad de qBittorrent se validó en vivo, pero no se añadió ningún torrent. Jackett se alcanzó desde Docker y devolvió XML en una consulta directa, pero la búsqueda global sufrió un timeout con el límite anterior.

## 4. Incidencia pendiente conocida: primera búsqueda de prueba

- La solicitud de prueba de **Nadie 2 (2025)** agotó sus cinco intentos cuando el timeout de Jackett era de 20 segundos.
- La consulta global de Jackett excedió ese timeout. Una consulta directa al único indexador configurado en esa instancia sí respondió dentro de un límite de 60 segundos y devolvió un resultado.
- Se cambió `JACKETT_TIMEOUT_SECONDS` a 60 y se verificó desde el worker que la configuración efectiva carga `60.0`.
- La solicitud de prueba quedó en estado `fallida`, con 5/5 intentos consumidos y el último error de comunicación con Jackett.
- **No se ha reactivado todavía.** El siguiente paso es reactivarla de forma controlada y observar el worker; no hacer una actualización manual de base de datos sin revisar primero el mecanismo seguro de reintento.
- La instancia de Jackett mostró un único indexador configurado. Para consultar más fuentes, el propietario debe configurar en Jackett las fuentes que esté autorizado a utilizar. No se presupone que una fuente sea legal por ser compatible con Torznab.

## 5. Configuración de almacenamiento conocida

- Jellyfin y qBittorrent están instalados de forma nativa en Windows, no en Docker.
- Biblioteca raíz de Jellyfin: `C:\\VIEWTV\\media`, con carpetas `peliculas` y `series`.
- Carpeta temporal configurada en qBittorrent: `C:\\VIEWTV\\media\\descargas_temporales`.
- En esta etapa no se ha implementado el movimiento automático desde la carpeta temporal a las bibliotecas finales.
- El worker todavía no necesita montar los archivos multimedia: qBittorrent escribe directamente en Windows. La organización posterior requerirá diseñar y probar cómo se moverán los archivos y cómo se actualizará Jellyfin.

## 6. Decisiones vigentes

- Selección manual obligatoria del torrent. El usuario decide qué versión descargar.
- No enviar nada a qBittorrent hasta que el usuario haya seleccionado explícitamente un resultado.
- Buscar en todos los indexadores habilitados en la instancia Jackett mediante el endpoint Torznab global; no limitar el código a un proveedor concreto.
- Adaptador Torznab genérico con XML; no parsear HTML.
- Jackett, no Prowlarr, como integración actual.
- Intel Quick Sync como ruta de aceleración a investigar; no NVENC.
- Usar fuentes y contenido propios, autorizados o de dominio público. La presencia de un resultado en Jackett no acredita derechos de distribución.
- No compartir ni versionar `.env`, claves API, PIN, cookies de sesión, tokens ni bases de datos locales.
- No modificar estilos ni componentes visuales sin autorización expresa.

## 7. Trabajo pendiente para completar el circuito

Orden recomendado para retomar:

1. **Reactivar y observar la solicitud de prueba.** Revisar el estado actual, aplicar el mecanismo controlado de reintento y confirmar que el worker utiliza timeout de 60 segundos.
2. **Validar búsqueda real.** Confirmar respuesta de Jackett, persistencia de resultados y presentación de todas las versiones disponibles, incluidas calidades distintas. Si se configuran más indexadores autorizados, comprobar que el endpoint global los consulta.
3. **Validar la API de selección en el entorno desplegado.** Confirmar que el perfil solo ve sus resultados y que la selección crea una fila `Descarga`, sin enviar todavía nada a qBittorrent.
4. **Prueba real de envío a qBittorrent, con autorización expresa del usuario.** Seleccionar un resultado de prueba autorizado, comprobar etiqueta, hash, categoría/ruta y que no se duplique tras una respuesta ambigua.
5. **Seguimiento de transferencia.** Implementar o validar consulta periódica del estado de qBittorrent, porcentaje, velocidad, errores, finalización y recuperación tras reiniciar worker/API/qBittorrent.
6. **Resiliencia.** Probar timeouts, qBittorrent no disponible, respuestas inesperadas sin hash, leases vencidos, intentos agotados y reintentos sin transferencias duplicadas.
7. **Organización de archivos.** Diseñar el paso seguro de `descargas_temporales` a `peliculas` o `series`; validar rutas, nombres, archivos incompletos y colisiones. No mover ni borrar archivos automáticamente hasta acordar la política.
8. **Integración Jellyfin.** Sincronizar el catálogo después de organizar un archivo de prueba propio/autorizado y verificar que aparece en la biblioteca. Probar reproducción desde Jellyfin y después desde VIEWTV.
9. **Interfaz de solicitudes y selección.** La API ya dispone de operaciones, pero falta completar/validar la experiencia de usuario para introducir un título, revisar calidades y elegir un resultado. Cualquier cambio visual requiere autorización expresa.
10. **Validación integral y documentación de operación.** Arranque limpio, recuperación tras reinicio, copias de seguridad, logs, seguridad de red y guía de uso.

## 8. Qué no debe darse por terminado

- No se ha completado una descarga real desde Jackett hasta qBittorrent.
- No se ha validado la transferencia completa ni el seguimiento de progreso.
- No se mueven automáticamente los archivos a las bibliotecas de Jellyfin.
- No se ha probado reproducción de una descarga gestionada por VIEWTV.
- No se ha completado el flujo de selección en la interfaz PWA.
- No se ha demostrado recuperación integral de todos los fallos del worker en un entorno real.
- La suite unitaria no sustituye las pruebas de integración de extremo a extremo.

## 9. Estado de pausa

El desarrollo queda en pausa tras la validación local de 129 pruebas y Ruff limpio. Al retomarlo, empezar por la solicitud de prueba fallida y el timeout de Jackett; no repetir la instalación/configuración de Docker, Jellyfin o qBittorrent salvo que las comprobaciones indiquen que ha cambiado el entorno.

No ejecutar `git reset`, `git clean`, cambiar de rama, eliminar archivos ni borrar volúmenes persistentes como parte de la reanudación. No publicar cambios en `main` sin autorización explícita.
