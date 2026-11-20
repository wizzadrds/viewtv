# VIEWTV — plan de salida rápida: primero producto, después mejoras

Fecha: 20-11-2026.
Regla del usuario: sacar la aplicación lo antes posible **con sus funciones
principales operativas**, y abordar después correcciones no críticas,
refinamientos y optimizaciones.

## Qué cuenta como "VIEWTV funciona"

Se considera **primera versión utilizable** cuando el usuario puede,
desde la interfaz, iniciar sesión con su propio perfil, consultar
su catálogo, generar una solicitud, elegir un resultado, comprobar
el estado de descarga y acceder a un medio disponible en Jellyfin.
Ninguna acción debe corromper la SQLite, duplicar descargas ni mover
archivos ajenos.

**La primera versión con organizador automático** exige además
que un contenido de prueba autorizado y completado se publique
una sola vez en el destino correcto y se detecte en Jellyfin,
con un mecanismo de reversión ensayado.

No declarar estas metas cumplidas basándose solo en salud de
contenedores, pruebas de endpoints públicos o un prototipo sintético.

## Hoja de ruta por bloqueos, sin ampliar requisitos

### Hito A — Estabilizar la aplicación base 0012 (HECHO PARCIALMENTE)

- [x] Diagnosticar API reiniciándose por imagen con migraciones 0008
  sobre SQLite 0012.
- [x] Respaldar SQLite de forma consistente, comprobar su integridad,
  revisión 0012 y SHA-256.
- [x] Recrear exclusivamente la API con la imagen 0012 ya definida
  en Compose; comprobar health y esquema Alembic.
- [x] Verificar interfaz, proxy API, perfiles y seguridad 401, Jellyfin.
- [x] **Sincronización automática del catálogo desplegada y verificada**:
  worker cada 30 minutos (primer intento tras 60 s,
  reintento a 5 minutos ante fallo), UI relee cada 5 minutos visible
  y al regresar a la pestaña. Eliminados ambos botones manuales.
  Primera consulta periódica real de Jellyfin: HTTP 200, **1 medio**
  procesado. Frontend y worker actualizados con imágenes nuevas;
  API y Jellyfin sin cambios, SQLite respaldada previamente.
- [x] El usuario confirmó que ya puede entrar en VIEWTV, consultar
  la biblioteca y **reproducir vídeos correctamente** en su navegador
  (20-11-2026), sin compartir contraseñas ni PIN.
- [x] **Descargas sin botón manual**: la consulta GET del seguimiento
  ya se repetía cada **15 segundos** con la pestaña visible.
  Se retiró el botón redundante y se añadió refresco inmediato al
  volver a la pestaña, preservando errores, paginación y autenticación.
  Ver [AVANCE-DESCARGAS-AUTOREFRESCO-VIEWTV-20261120.md](AVANCE-DESCARGAS-AUTOREFRESCO-VIEWTV-20261120.md).
- [ ] La operación de cierre de sesión no se ha ensayado por separado.
- [x] Diagnóstico de la única solicitud `fallida`, sin acceder a su
  título, URLs o perfiles: fallo histórico de comunicación con
  Jackett y reintentos agotados. No se ha borrado ni reintentado.
  Jackett ya responde en una consulta de estado, pero aún falta
  comprobar una búsqueda nueva desde la aplicación.

### Hito B — Solicitudes y descarga de prueba (EN CURSO)

- [x] Añadida y desplegada la pestaña **«Buscar y pedir»**. Permite
  crear una solicitud manual de película o serie (año opcional),
  consultar solicitudes y resultados, y seleccionar uno con las
  rutas de API existentes. Refresca listas cada 10 segundos y al
  volver a la pestaña. No dispara acciones POST por abrirla.
  Ver [AVANCE-SOLICITUDES-UI-VIEWTV-20261120.md](AVANCE-SOLICITUDES-UI-VIEWTV-20261120.md).
- [x] Recorrido **sintético completo** probado: POST manual de solicitud,
  búsqueda Torznab con `httpx.MockTransport` sin red, worker/lease/SQLite
  ficticios, GET de resultados, selección, GET de Descargas, duplicados,
  fallo sin resultados y aislamiento entre perfiles. No se tocó qBittorrent
  real ni la SQLite productiva.
- [x] Separado el permiso de **añadir torrents a qBittorrent** del permiso
  de **iniciarlos**. `VIEWTV_ENABLE_TORRENT_SUBMIT=false` (nuevo, por
  defecto) deja seleccionada una descarga sin darla de alta en qBittorrent.
  `VIEWTV_ENABLE_DOWNLOAD_START=false` sigue vigente. Ninguno se
  activa sin autorización del ensayo.
- [x] **Preparado y desplegado el filtro de un solo ensayo**:
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID` debe indicar una ID positiva
  específica para poder enviar un torrent, incluso si se activa el
  permiso general. El lease se filtra por esa ID; no se reclama
  ninguna otra descarga. Además se exige staging Windows conocido
  `C:\VIEWTV\media\descargas_temporales`, un único hash/etiqueta
  y estado detenido verificados con HTTP simulado, o se falla cerrado.
  **Los tres controles siguen desactivados/vacíos en producción**.
  Ver [AVANCE-ENSAYO-TORRENT-UNICO-VIEWTV-20261120.md](AVANCE-ENSAYO-TORRENT-UNICO-VIEWTV-20261120.md).
- [ ] **Validación real pendiente con el usuario:** crear una solicitud
  autorizada desde la interfaz, esperar resultados de Jackett y
  seleccionar uno; no se han creado solicitudes durante las pruebas.
  Documentación en
  [AVANCE-SELECCION-SIN-ENVIO-VIEWTV-20261120.md](AVANCE-SELECCION-SIN-ENVIO-VIEWTV-20261120.md).
- [x] Consultas GET de conectividad: Jackett responde a la lista de
  indexadores con uno configurado; qBittorrent responde a la lectura
  de versión. Sin iniciar ni modificar ningún torrent.
- [x] **Preflight read-only de Windows y qBittorrent**: la carpeta
  `C:\VIEWTV\media\descargas_temporales` y su padre existen, son
  directorios y no son puntos de redirección. GET de preferencias
  qBittorrent: ruta de descarga predeterminada **igual** a staging,
  ruta temporal alternativa **distinta pero desactivada**. No se
  enumeraron contenidos ni se modificaron torrents o rutas.
- [x] **Búsquedas GET reales sin solicitudes ni descargas**: Jackett
  respondió sin errores a una búsqueda `movie` de «Big Buck Bunny»
  y una búsqueda general de «ubuntu», pero devolvió **cero resultados
  en ambas**. Confirma conectividad y parsing, **no** disponibilidad
  de resultados ni funcionamiento final de la búsqueda. Procedimiento
  y pruebas en
  [AVANCE-PREFLIGHT-RUTAS-Y-PROVEEDOR-VIEWTV-20261120.md](AVANCE-PREFLIGHT-RUTAS-Y-PROVEEDOR-VIEWTV-20261120.md).
- [x] **Capacidades Torznab del proveedor comprobadas en vivo**:
  de 654 indexadores listados en Jackett, **uno configurado**.
  Este admite `search`, `movie-search`, `tv-search` y búsqueda
  por título `q` en los tres modos. El endpoint administrativo
  de estado **no facilitó un estado verificable** mediante GET,
  por lo que NO se considera saludable solo por las capacidades.
  Hay pruebas y diagnóstico sin revelar el nombre del indexador
  en
  [AVANCE-CAPACIDADES-JACKETT-VIEWTV-20261120.md](AVANCE-CAPACIDADES-JACKETT-VIEWTV-20261120.md).
- [ ] **Bloqueador de búsqueda real**: probar un título legítimo
  desde «Buscar y pedir» y comprobar en el panel de Jackett
  el indexador configurado y sus pruebas propias si vuelve a salir
  `sin_resultados`. No inventar corrección de la API cuando el
  proveedor responde 0 y declara capacidades correctas.
- [ ] Demostrar seguimiento del trabajo elegido y estados de fallo.
- [x] **Inicio individual implantado y ensayado sin red**: la orden
  de arranque utiliza la **misma ID canónica** de
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID`; sin ID positiva, incluso
  con `VIEWTV_ENABLE_DOWNLOAD_START=true`, no reclama ni
  inicia nada. El lease se filtra transaccionalmente por ID.
  Exige una coincidencia única de hash, etiqueta y staging;
  solo ordena iniciar ese hash. Pruebas con dos descargas
  ficticias, qBittorrent simulado y recuperación sin doble POST.
  **Worker desplegado** con imagen `viewtv:inicio-torrent-unico-0012`,
  flags de alta e inicio en `false` e ID vacía. Backend completo
  **684 pruebas aprobadas**, smoke posterior **10/10**.
  Ver [AVANCE-INICIO-TORRENT-UNICO-VIEWTV-20261120.md](AVANCE-INICIO-TORRENT-UNICO-VIEWTV-20261120.md).
- [ ] **Alta e inicio reales pendientes**: mantener
  `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID` vacío y
  `VIEWTV_ENABLE_DOWNLOAD_START=false` hasta comprobar una
  búsqueda con resultados y una descarga autorizada. La ruta
  de staging existe y coincide con la configuración de qBittorrent;
  todavía falta comprobar la operación real y la identidad del
  torrent seleccionado. Activar primero el alta detenida y
  después el inicio de esa misma ID, con autorización específica,
  respaldo y reversión manual.
- [ ] Establecer procedimiento reversible; no habilitar
  ejecuciones masivas ni cambios de biblioteca por defecto.

### Hito C — Organizador mínimo seguro 0013 (EN CURSO, SOLO LABORATORIO)

- [x] **Puente organización → Jellyfin probado con un vídeo ficticio**:
  la cola y el copiador bajo `/tmp` publican el medio y confirman
  `organizada` en SQLite; solo entonces se solicita mediante
  `POST /Library/Refresh` un escaneo a un Jellyfin simulado.
  El catálogo de VIEWTV no muestra el medio hasta que el
  escaneo **ha terminado** y se sincroniza el catálogo. Si falla
  la solicitud, queda `publicada_escaneo_pendiente` y puede
  repetirse el escaneo **sin copiar de nuevo**. No hay integración
  en el worker productivo ni POST al Jellyfin real.
  Ver [AVANCE-PUENTE-ORGANIZADOR-JELLYFIN-VIEWTV-20261120.md](AVANCE-PUENTE-ORGANIZADOR-JELLYFIN-VIEWTV-20261120.md).
- [ ] Reutilizar la validación de lease, torrent y permisos
  ya probada en sandbox; no añadir nuevas mejoras ajenas a salida.
- [ ] Integrar una autoridad durable única y separada del worker,
  sin rutas de publicación que eludan la autorización.
- [x] Probar un único medio sintético hasta catálogo visible
  en SQLite de laboratorio, con un destino, copia sin sobrescribir,
  escaneo simulado y recuperación sin repetir publicación.
- [x] **Conectar la prueba Docker → publicación NTFS Windows →
  escaneo y catálogo Jellyfin ficticios** en un solo ensayo:
  8 controles correctos en sandbox nuevo y marcado bajo
  `C:\Users\Public`, con vídeo y subtítulo sintéticos.
  Antes de publicar: 0 escaneos; tras reconciliación firmada
  Windows, `POST /Library/Refresh` simulado y catálogo
  visible solo tras finalizar el escaneo simulado. Las fuentes
  quedan intactas, no hay sobrescritura ni escritura en medios
  reales. Ver
  [AVANCE-CADENA-NTFS-JELLYFIN-VIEWTV-20261120.md](AVANCE-CADENA-NTFS-JELLYFIN-VIEWTV-20261120.md).
- [ ] Integrar una autoridad **operativa** de publicación confinada
  en Windows, con verificación de torrent/lease y comunicación
  autenticada, y probarla en una biblioteca de demostración.
  **La prueba en C:\Users\Public NO equivale a publicación real.**
- [ ] Demostrar movimiento seguro y detección en Jellyfin real
  con datos expresamente autorizados antes de habilitar automatización.

### Hito D — Publicación controlada y cierre (PENDIENTE)

- [ ] Respaldos consistentes de SQLite y configuración, comprobados.
- [ ] Pruebas de autenticación, catálogo, búsqueda, selección,
  descarga, seguimiento, publicación y reproducción.
- [ ] Simular reversión con copias, sin sobrescribir datos vivos.
- [ ] Autorización explícita para activar funcionalidades
  que inicien torrents, muevan medios o cambien producción.
- [ ] Despliegue gradual y monitorización de la API/worker.
- [ ] Cerrar PR en el momento autorizado, no antes.

## Dejar para DESPUÉS de una primera versión funcional

- Mejoras cosméticas y de rendimiento no bloqueantes.
- Nuevas funciones opcionales y automatizaciones complementarias.
- Casuística adicional de errores que no afecte integridad,
  privacidad o seguridad de las operaciones esenciales.
- Pulido o ampliación indefinida de prototipos sandbox ya validados.

## Estado verificado al elaborar el plan

- API **reparada**, imagen `viewtv:predeploy-0012-release`,
  saludable y Alembic en revisión 0012.
- UI Next.js en `127.0.0.1:3000` (HTTP 200),
  proxy a API (HTTP 200), ruta de perfiles (HTTP 200).
- Jellyfin saludable en `127.0.0.1:8097` (HTTP 200).
- Worker activo y descarga automática desactivada.
- Script de humo de solo lectura: **10/10 correcto**.
- Inventario SQLite de solo lectura: 2 perfiles activos, 2 medios,
  1 disponible en Jellyfin, 1 solicitud fallida por comunicación
  con Jackett y 0 descargas. La solicitud agotó sus reintentos.
- Consultas de conectividad Jackett y qBittorrent: **OK**;
  no se han lanzado torrents ni búsquedas.
- Sincronización automática de Jellyfin **activa en producción**,
  metadata refrescada en la primera ejecución sin mover archivos.
  Primer paso seguro del catálogo automatizado; conserva rollback
  transaccional ante un fallo de consulta.
- Panel «Mis descargas» con auto-GET cada 15 segundos, sin botón
  «Actualizar», y consulta inmediata al volver a la pestaña;
  solo consulta estados, sin iniciar torrents.
- Sección «Buscar y pedir» desplegada, con formulario y resultados
  del perfil autenticado, actualización cada 10 segundos y acciones
  explícitas de solicitud/selección. La API ya exponía las cuatro
  operaciones y no requirió cambios. **Aún falta una prueba con una
  solicitud real autorizada**; no se ha iniciado ningún torrent.
- Worker con filtros **por una sola ID tanto para el envío como
  para el inicio**, y comprobación de staging, etiqueta, hash y
  estado de qBittorrent. Probados GET-POST-GET del alta y GET-POST
  del inicio con clientes HTTP simulados sin red. Ambos permisos
  permanecen `false` y la ID vacía en producción. **La ruta
  Windows y una transferencia real siguen sin verificarse**.
- Diagnóstico registrado en
  [AVANCE-SALIDA-VIEWTV-CONEXIONES-Y-COLA-20261120.md](AVANCE-SALIDA-VIEWTV-CONEXIONES-Y-COLA-20261120.md).
- Entrega de catálogo automático en
  [AVANCE-CATALOGO-AUTOMATICO-VIEWTV-20261120.md](AVANCE-CATALOGO-AUTOMATICO-VIEWTV-20261120.md),
  con respaldo de SQLite, imágenes de rollback y pruebas.
- Puente de laboratorio **organización confirmada → escaneo
  Jellyfin simulado → actualización de catálogo** implementado.
  Integración posterior ensayada **en NTFS real sobre una carpeta
  de pruebas Windows**, acoplando Docker, publicación y
  reconciliación Windows y catálogo Jellyfin falso.
  En producción el worker **no ejecuta organización ni solicita
  escaneos por esta ruta**.
- PR #2 sigue en borrador; no significa que 0013 esté desplegado.
- El usuario **sí ha confirmado** acceso a VIEWTV y reproducción
  de vídeos satisfactoria. No se ha verificado por separado
  la operación de cierre de sesión.
- **NO verificados aún:** una búsqueda nueva con resultados desde
  la interfaz, selección, una descarga real, seguimiento completo
  y organización automática. Las consultas GET de prueba sí
  alcanzaron Jackett, pero ambas devolvieron cero resultados.
  El único proveedor configurado anuncia compatibilidad con
  búsqueda general, de películas y series; **su estado operativo
  no quedó confirmado** por la API administrativa.
  La carpeta Windows y la preferencia por defecto de qBittorrent
  coinciden; eso no sustituye el ensayo de una transferencia.

## Regla obligatoria de documentación y publicación de avances

A petición expresa del usuario, **este documento es el plan maestro de
salida** y se actualiza con el estado real de cada hito. Cada avance
importante debe contener:

1. Qué problema del producto desbloquea y qué objetivo de uso valida.
2. Evidencia exacta, pruebas que pasaron y funciones aún no probadas.
3. Copia verificable antes de editar archivos existentes o SQLite.
4. Informe nuevo o actualizado en `docs/`, referencias al código y
   procedimiento de reversión cuando corresponda.
5. Commit descriptivo en español, push solo a
   `viewtv-seguimiento-descargas-0012` y verificación del PR #2
   **abierto, en borrador y sin fusionar**.

La regla de priorización es **función que bloquea la aplicación >
prueba de esa función > errores no críticos > mejoras**. Nunca
confundir servicio saludable con autenticación, búsqueda, descarga o
reproducción ya verificadas. No acceder a PIN ni secretos del usuario;
las pruebas con cambios reales de torrents y biblioteca necesitan
una autorización de ensayo específica.

## Regla de estimación

No repetir una estimación de varias semanas sin pruebas.
Con la API arreglada, el próximo bloqueador real se determina
por la primera prueba funcional del usuario y del circuito de
descarga. Registrar qué falla y cuánto trabajo concreto exige
antes de comprometer horas o una fecha final.
