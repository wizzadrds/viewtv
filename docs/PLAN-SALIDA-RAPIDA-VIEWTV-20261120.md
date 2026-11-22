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
  fallo sin resultados y aislamiento entre perfiles. Revalidado en
  contenedor aislado sin red el 20-11-2026: **6/6 comprobaciones** de
  creación, cola, resultados, permisos por perfil, selección y seguimiento
  con SQLite en memoria y Jackett simulado. No se tocó qBittorrent
  real ni la SQLite productiva. Ver
  [AVANCE-BUSQUEDA-RESULTADOS-VIEWTV-20261120.md](AVANCE-BUSQUEDA-RESULTADOS-VIEWTV-20261120.md).
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
- [x] **Solicitud real creada y procesada desde la interfaz**:
  el usuario confirmó «Nadie 2» sin año en `sin_resultados` y otra
  solicitud anterior con año 2025 `fallida`. El worker registró
  la solicitud 2 procesada con cero resultados seleccionables.
  No se inició descarga. Diagnóstico del proveedor en
  [AVANCE-BUSQUEDA-NADIE2-VIEWTV-20261120.md](AVANCE-BUSQUEDA-NADIE2-VIEWTV-20261120.md).
- [x] **Primera selección real desde PWA diagnosticada**:
  el usuario eligió por error un episodio de otra serie:
  descarga **1**, solicitud **3**, `seleccionada`/0 %, sin envío.
- [x] **Filtro de relevancia y limpieza de solicitudes desplegados**:
  de 62 resultados históricos solo 2 coinciden con título/tipo.
  Worker filtra antes de guardar, API filtra al listar y rechaza
  seleccionar candidatos ajenos. PWA muestra solo solicitudes
  activas y ofrece «Ver historial» sin eliminar registros.
  Permite «Deshacer selección» únicamente si aún no se envió.
  Backend **778/778**, ensayo con copia real **4/4**, frontend
  compilado, smoke 0012 **10/10**. Ver
  [AVANCE-RELEVANCIA-LIMPIEZA-SOLICITUDES-20261120.md](AVANCE-RELEVANCIA-LIMPIEZA-SOLICITUDES-20261120.md).
- [ ] **Validación visual final pendiente:** usuario recarga PWA,
  deshace expresamente la selección #1 y elige un resultado
  adecuado que tenga derecho a obtener. No activar descargas.
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
- [x] **Búsqueda GET con resultados reales**: desde el worker de
  producción, Torznab `movie` y `search` con «Ocho apellidos vascos»
  devolvieron **4 resultados cada una, todos con enlace seleccionable**;
  el conversor del worker mantuvo **4/4 aptos para guardar** en ambas
  modalidades, sin escribir SQLite.
  No se creó ninguna solicitud ni se descargó contenido. Jackett
  funciona para este título; no hace falta modificar Cloudflare,
  FlareSolverr ni otros indexadores para esta comprobación.
  Ver [AVANCE-BUSQUEDA-RESULTADOS-VIEWTV-20261120.md](AVANCE-BUSQUEDA-RESULTADOS-VIEWTV-20261120.md).
- [x] **Diagnóstico del cero en «Nadie 2»**: la PWA registró una
  solicitud real que terminó en `sin_resultados`; el worker corroboró
  cero elementos. Jackett GET con `Nadie 2` también dio cero, pero
  `Nadie 2 2025` dio **62 registros aptos**, de los cuales solo
  **3** contienen título relacionado y **2** mencionan 2025.
  `Nobody 2` y `Nobody 2 2025` dieron cero. No hay evidencia
  de que cambiar Cloudflare/FlareSolverr resuelva el problema.
  Ver [AVANCE-BUSQUEDA-NADIE2-VIEWTV-20261120.md](AVANCE-BUSQUEDA-NADIE2-VIEWTV-20261120.md).
- [x] **Solicitud real con resultados disponibles en PWA**:
  el usuario confirmó que una solicitud de «Nadie 2» pasó a
  `esperando_seleccion`, pero «Ver resultados» fallaba con HTTP 500.
  El log de API demostró que `publicado_en` era un `datetime`
  incompatible con la anotación de respuesta. Se normalizó a ISO 8601,
  se ensayó con fechas reales/nulas y con una copia SQLite productiva;
  HTTP 200 y mismas filas, sin URLs internas. API corregida
  `viewtv:resultados-fecha-0012` desplegada sola y sana,
  smoke 10/10. Informe:
  [AVANCE-CORRECCION-RESULTADOS-500-VIEWTV-20261120.md](AVANCE-CORRECCION-RESULTADOS-500-VIEWTV-20261120.md).
- [x] **La PWA real permite ver resultados y seleccionar**:
  el usuario lo confirmó y creó una selección, pero era un
  episodio ajeno. Corregido por filtro en API y worker.
- [x] **Usuario detectó otra selección incorrecta**: la PWA
  mostró «Nadie.2.2025.DVDRip.SPANISH», solicitud #3, ID 1.
  Aunque el título superaba el filtro, el usuario confirmó que
  **no era el torrent correcto** y lo eliminó personalmente
  de qBittorrent. No intentar recuperarlo ni iniciarlo.
- [ ] Demostrar seguimiento del trabajo elegido y estados de fallo.
- [x] **Inicio individual implantado y ensayado sin red**: la orden
  de arranque utiliza la **misma ID canónica** de
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID`; sin ID positiva, incluso
  con `VIEWTV_ENABLE_DOWNLOAD_START=true`, no reclama ni
  inicia nada. El lease se filtra transaccionalmente por ID.
  Exige una coincidencia única de hash, etiqueta y staging;
  solo ordena iniciar ese hash. Pruebas con dos descargas
  ficticias, qBittorrent simulado y recuperación sin doble POST.
  **Imagen original** `viewtv:inicio-torrent-unico-0012`; actualmente
  worker `viewtv:qbit-async-0012`, que conserva los mismos filtros
  por ID, envío e inicio en `false` e ID vacía. Prueba histórica
  **684 aprobadas**; última suite completa **796/796** y smoke **10/10**.
  Ver [AVANCE-INICIO-TORRENT-UNICO-VIEWTV-20261120.md](AVANCE-INICIO-TORRENT-UNICO-VIEWTV-20261120.md).
- [x] **Ensayo real de alta DETENIDA de ID 1, con permiso
  específico del usuario**: GET de Jackett válido, tres intentos
  de envío controlados en total, último POST HTTP 202 asíncrono.
  qBittorrent mostró transitoriamente un torrent detenido con
  etiqueta y staging verificados; VIEWTV lo reconcilió sin otro
  POST y guardó hash y estado `enviada`. Sin embargo, posteriores
  GET por etiqueta y hash dieron **cero** tras la **eliminación
  voluntaria realizada por el usuario al reconocer el torrent
  incorrecto**. No volver a añadirlo ni iniciarlo.
- [x] **Compatibilidad qBittorrent 5.3 y prevención de duplicados**:
  se corrigió la URL interna Jackett para qBit Windows, se reconoció
  JSON/HTTP 202 como alta pendiente y se implementó consulta posterior
  sin un segundo POST. Worker `viewtv:qbit-async-0012` desplegado
  con envío/inicio `false`, ID vacía; backend **796/796**, smoke
  **10/10**. Informe y respaldos:
  [AVANCE-ALTA-DETENIDA-QBIT-ASYNC-0012-20261120.md](AVANCE-ALTA-DETENIDA-QBIT-ASYNC-0012-20261120.md).
- [x] **Corregir interpretación del torrent eliminado**:
  el usuario confirmó que **él mismo reanudó, detuvo y eliminó**
  el torrent porque no correspondía al contenido buscado.
  Por tanto, la desaparición no fue un fallo de estabilidad
  atribuido a qBittorrent. La fila SQLite original sigue
  `enviada`/`inicio=pendiente`, sin transferencia existente.
- [x] **Descarte explícito, seguro y con historial**: API autenticada
  `POST /solicitudes/descargas/{id}/descartar-incorrecta` comprueba
  por hash y etiqueta que el torrent ya no existe; exige 0 %,
  inicio nunca intentado y ausencia de leases. Conserva la descarga
  en SQLite como `fallida` con marca de descarte del usuario
  (sin nueva migración), cancela la solicitud y la oculta por
  defecto de «Mis descargas». El botón requiere confirmación.
  **805/805 tests** y **4/4** en copia real aislada, frontend compilado,
  smoke **10/10** tras desplegar únicamente API/frontend. Ver
  [AVANCE-DESCARTE-SELECCION-INCORRECTA-20261121.md](AVANCE-DESCARTE-SELECCION-INCORRECTA-20261121.md).
- [x] **Usuario descartó la descarga #1**: SQLite real muestra
  `estado=fallida` y solicitud #3 `cancelada`, sin torrent
  en qBittorrent. Se conserva el histórico.
- [x] **Detectar tamaño real y torrent duplicado en nueva selección**:
  solicitud #4, descarga #2 «Nadie.2.2025.DVDRip.SPANISH».
  Dos URLs diferentes de Jackett devuelven el **mismo infohash**,
  que coincide con el hash histórico de #1: el torrent ya
  descartado. El indexador anuncia 1,4 GiB, pero los metadatos
  reales señalan **16,47 GiB** (17.686.540.911 bytes), dos
  archivos (uno vídeo). **Caso histórico:** esa selección
  fue deshecha y la ID canónica 2 se reutilizó después en
  la nueva solicitud #6 (véase abajo).
- [x] **Validación de metadatos antes de alta en qBittorrent**:
  nuevo lector bencode solo para el Jackett configurado,
  sin redirecciones, con límite 4MB, cotejo de tamaño real
  y hash contra anteriores descartes del perfil. Si el
  tamaño difiere en más de la tolerancia o el hash ya
  fue descartado, bloquea ANTES del POST y del intento.
  Worker `viewtv:validacion-tamano-0012` desplegado
  con envío e inicio `false`, ID autorizada vacía.
  Tests **829/829**, focales **68/68**, sin alterar
  SQLite ni otros torrents. Informe:
  [AVANCE-VALIDACION-TAMANO-TORRENT-20261121.md](AVANCE-VALIDACION-TAMANO-TORRENT-20261121.md).
- [x] **Nueva selección tras descartar «Nadie 2»**:
  la ID canónica 2 ya pertenece a solicitud #6
  `La.Odisea.2026.4K.4K.SPANISH` (seleccionada,
  0 intentos y sin hash). Jackett anuncia **20 GiB**
  pero el archivo .torrent realmente contiene
  **33.260.748.236 bytes** (~33,26 GB). **Hecho
  histórico:** la selección fue deshecha. La discrepancia
  de tamaños por sí sola ya no bloquea resultados nuevos.
- [x] **Hito anterior (ya sustituido): tamaño real bajo demanda**:
  API autenticada `GET /solicitudes/{id}/resultados/{id}/verificacion`
  consulta solo metadatos de Jackett de forma bajo demanda,
  compara el tamaño y detecta hashes ya descartados del perfil;
  no expone URLs ni hashes. La PWA muestra «Comprobar tamaño
  real», tamaño anunciado y real, y bloquea «Seleccionar»
  salvo estado apto. La API repite la verificación previa a
  POST para enlaces directos Jackett, sin red dentro del
  bloqueo de SQLite. API/PWA desplegadas por separado,
  worker inalterado y flags false. **835/835 tests**,
  **5/5 pruebas sobre copia SQLite real** y smoke
  **10/10**. Informe:
  [AVANCE-PRESELECCION-TAMANO-REAL-20261121.md](AVANCE-PRESELECCION-TAMANO-REAL-20261121.md).
- [x] **La solicitud #6 volvió a «esperando_seleccion»**:
  tras deshacer la selección previa, la SQLite real no contiene
  ninguna descarga activa de #6; los cinco resultados permanecen.
  No se envió el resultado a qBittorrent.
- [x] **La fuente canónica de tamaño es el .torrent, NO Jackett**:
  el usuario pidió dejar de confiar en los tamaños publicados.
  Ahora la API muestra tamaño real y guarda tamaño/hash del
  metainfo al seleccionar; la PWA muestra «por comprobar»
  antes del GET y la diferencia de Jackett como advertencia
  secundaria. **La disparidad no bloquea por sí sola.**
  El worker vuelve a comprobar el metainfo y guarda sus
  valores reales bajo lease antes de un futuro envío,
  manteniendo bloqueos por infohash descartado, metadatos
  inválidos o identidad distinta y sin iniciar torrents.
  Se desplegaron por separado API/frontend/worker con
  envío e inicio `false` e ID permitida vacía.
  **836/836** pruebas backend, **116/116** focales,
  **6/6** en copia SQLite real y **10/10** smoke.
  Informe:
  [AVANCE-TAMANO-CANONICO-DESDE-TORRENT-20261121.md](AVANCE-TAMANO-CANONICO-DESDE-TORRENT-20261121.md).
- [x] **Pantalla sin botón «Comprobar tamaño real»**:
  los resultados obtienen el tamaño del .torrent
  automáticamente al abrirse, con tres GET concurrentes
  como máximo. La PWA presenta **una sola cifra real**
  por candidato, sin datos de tamaño de Jackett.
  «Seleccionar» pasa a **«Descargar»**.
- [x] **Opt-in de envíos e inicios automáticos para nuevas
  selecciones**: `VIEWTV_ENABLE_AUTO_DOWNLOAD=true`,
  corte durable `VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1`
  (máximo ID al desplegar). El worker admite solo ID
  posteriores, una descarga activa cada vez, ruta de
  staging fija y torrent detenido hasta orden de inicio
  individual. No reanuda pausas manuales ni toca torrents
  ajenos a VIEWTV; rechaza hashes preexistentes ajenos,
  previamente descartados o que cambian de identidad.
  Las antiguas flags globales permanecen `false`.
  API no se recreó; solo worker y frontend actualizados.
  Tests **858/858**, focales **73/73**, smoke **10/10**,
  primera comprobación real sin candidatas activas.
  Informe:
  [AVANCE-TAMANO-UNICO-Y-DESCARGAS-AUTOMATICAS-20261121.md](AVANCE-TAMANO-UNICO-Y-DESCARGAS-AUTOMATICAS-20261121.md).
- [x] **Explicación y pantalla para torrents descartados duplicados**:
  en solicitud #4 los dos resultados «Nadie 2» (4K y DVDRip)
  devuelven **exactamente el infohash del torrent que el usuario
  eliminó**; ambos tienen 16,47 GiB reales, por lo que
  no son alternativas distintas y deben seguir bloqueados.
  Los cinco resultados de solicitud #6 devolvieron cinco
  infohash diferentes, ninguno igual al descartado.
  La PWA muestra «Ya descartado» en lugar de «Descargar»
  y explica las coincidencias aunque cambien los nombres;
  cuando todos están descartados muestra aviso general.
  Solo la PWA se recreó; worker automático, API,
  qBittorrent, SQLite y Jellyfin permanecen intactos.
  Compilación Next.js PASS; smoke producción readonly 10/10.
  [AVANCE-RESULTADOS-DESCARTADOS-CLAROS-20261121.md](AVANCE-RESULTADOS-DESCARTADOS-CLAROS-20261121.md).
- [x] **Enlaces de Jackett 404: diferenciación y rebúsqueda**:
  nueva prueba solo de metadatos demuestra que los dos
  enlaces guardados de #4, y también los dos de una
  búsqueda nueva directa, devuelven **HTTP 404**.
  El Jackett responde en la raíz; el enlace ofrecido
  por la fuente no es utilizable, aunque un examen
  anterior había demostrado que ambos infohash eran
  el torrent descartado. PWA distingue «Enlace no
  disponible» (no comprobable ahora) de «Ya descartado»
  (identidad confirmada), y ofrece «Actualizar
  resultados» sin iniciar ninguna descarga.
  API añade endpoint autenticado 202 que reencola
  solo solicitudes propias y sin descargas bajo
  `BEGIN IMMEDIATE`; preserva los resultados
  antiguos hasta terminar la búsqueda. El worker
  automático no fue recreado y retiene corte ID 1.
  Tests **864/864**, focales **73/73**,
  compilación Next.js/TypeScript PASS y smoke
  producción **10/10**; API y frontend healthy.
  **Rebuscar no soluciona necesariamente los 404:
  puede requerir corregir la fuente/indexador Jackett.**
  Informe:
  [AVANCE-ENLACES-JACKETT-404-REBUSQUEDA-20261121.md](AVANCE-ENLACES-JACKETT-404-REBUSQUEDA-20261121.md).
- [x] **POLÍTICA ACTUAL — permitir repetir torrents previamente descartados**:
  el usuario pidió retirar el veto, los avisos y las
  confirmaciones adicionales por descargas antiguas y
  entradas repetidas. API, PWA y worker desplegados:
  un `.torrent` legible se puede elegir con «Descargar»
  aun si su infohash coincide con un descarte antiguo.
  NO se recuperan ni arrancan selecciones históricas;
  solo nuevas selecciones por el usuario (umbral ID 1).
  Se mantiene la comprobación de metainfo e identidad,
  la protección de torrents ajenos en qBittorrent y
  los errores de enlaces HTTP 404/410.
  **864/864** tests completos, **90/90** focales,
  prueba en copia SQLite real sin efectos,
  Next.js/TypeScript PASS y smoke **10/10**;
  API/PWA healthy y worker running. No se añadió
  ni inició torrent alguno al desplegar.
  Los apartados anteriores sobre «Ya descartado» y
  «deben seguir bloqueados» describen versiones
  PREVIAS y quedan sustituidos por esta decisión.
  Informe:
  [AVANCE-SIN-BLOQUEO-POR-DESCARTADO-20261121.md](AVANCE-SIN-BLOQUEO-POR-DESCARTADO-20261121.md).
- [x] **Primera transferencia real completada y verificada**:
  el usuario seleccionó «Nadie 2» desde solicitud #7,
  nueva descarga ID 2, qBittorrent registrada/arrancada
  en staging propio y progreso **100 %**. La validación
  de archivos finalizó como `verificada` tras corregir
  el bug de columnas 0013 sobre esquema 0012.
  Posteriormente se publicó puntualmente en Películas,
  se comprobó portada/sinopsis en Jellyfin y se sincronizó
  VIEWTV; véase Hito C. La organización automática
  GENERAL sigue pendiente. El torrent histórico #1
  sigue fallido, sin reactivación.
- [x] **Despliegue reversible**:
  `scripts/viewtv_compose_automatico_0012.sh` permite
  rollback independiente de frontend y worker sin
  migraciones ni tocar la biblioteca. Mantener solo
  una descarga VIEWTV activa por seguridad.

- [x] **Reproducción HLS real de MKV HEVC/E-AC3 en VIEWTV**:
  después de catalogar «Nadie 2», el navegador mostraba
  «No hay una fuente Direct Play disponible» porque
  el perfil de dispositivo no anunciaba transcodificación.
  Se añadió HLS H.264/AAC (bitrate inicial 8 Mb/s),
  proxy privado con HMAC y rutas con 4 horas de validez,
  y reproductor `hls.js 1.7.4`, manteniendo Direct
  Play preferido para archivos compatibles.
  Jellyfin real negocia `listo, hls`, master y variante
  HTTP 200 con **1340 fragmentos** reescritos a URL
  protegidas sin clave API, primer fragmento real
  HTTP 200, `video/mp2t`, 32 KiB recibidos.
  Backend **879/879** tests, Next.js/TypeScript PASS,
  smoke **10/10**. API/PWA nuevas healthy, worker sin
  recrear; no cambios de película ni de SQLite.
  **Confirmación posterior del usuario (21/11/2026): la
  película sí se ve bien.** No equivale a ensayo de
  reproducción completa de dos horas. Jellyfin sin
  aceleración de hardware puede tener límites con HEVC 4K.
- [x] **Pantalla negra 00:00: conectado el vídeo real a hls.js**:
  la PWA montaba el elemento `<video>` SIN `ref={videoRef}`,
  por lo que el efecto de HLS retornaba sin ejecutar
  `player.attachMedia(video)` y la pantalla quedaba
  negra sin duración ni fuente. Ref conectada al JSX,
  test de regresión, frontend **11/11 PASS**, compilación
  Next.js/TypeScript PASS, preflight Compose PASS.
  Se recreó **solo frontend** con imagen
  `viewtv-frontend:hls-video-ref-0012`, healthy, sin
  tocar API, worker, descargas ni Jellyfin.
  Smoke read-only **10/10**. El usuario confirmó después
  de la recarga que «Nadie 2» se ve bien: prueba visual
  del navegador **superada**. No se han observado dos horas sin cortes.
  Informe:
  [AVANCE-VIDEO-NEGRO-HLS-REF-20261121.md](AVANCE-VIDEO-NEGRO-HLS-REF-20261121.md).
- [x] **Backup diario deja de recrear la API antigua**:
  la tarea Windows de las 03:00 ejecutaba el script WSL
  que invocaba `docker compose up -d api` sin los
  overrides de producción. Eso volvía a `viewtv:local`
  y provocaba reinicios por revisión SQLite 0012.
  Con respaldo archivado se eliminó únicamente ese
  `up -d`; ahora verifica que la API actual está
  levantada y usa `docker compose exec -T api`
  para la copia sin reconstruirla. Tras restaurar la
  imagen HLS, la API volvió a `healthy`; smoke PASS.
  Informe:
  [AVANCE-HLS-REPRODUCCION-NADIE2-20261121.md](AVANCE-HLS-REPRODUCCION-NADIE2-20261121.md).

### Hito C — Organizador mínimo seguro 0013 (EN CURSO, NO DESPLEGADO)

- [x] **Descarga real #2 terminada y verificación 0012 reparada**:
  el usuario pidió que apareciese automáticamente en Películas con
  carátula y metadatos. qBittorrent tiene un MKV completo de
  **16,47 GiB** más un `.url` promocional. La verificación de
  archivos ya pasaba, pero `finish_claimed_verification()`
  escribía campos 0013 ausentes de la DB 0012. Se corrigió
  esa incompatibilidad, se desplegó **solo el worker** y la
  ID 2 pasó realmente a **`verificada`**. Backend completo
  **865/865**, focales **98/98**, smoke **10/10**.
  Se preservaron los torrents ajenos, Jellyfin y la biblioteca.
- [x] **Plan para publicar solo MKV con año apto para Jellyfin**:
  planificador 0013 ya omite `.url` sin copiarlo ni ejecutarlo,
  mantiene rechazo de ejecutables, y en solicitud manual sin año
  detecta el único `(2025)` del nombre del vídeo para proponer
  `Peliculas/Nadie 2 (2025)/Nadie 2 (2025).mkv`. Solo
  laboratorio/planificación; no despliegue de publicación.
  Los proveedores de imágenes TheMovieDb y OMDb están
  habilitados en Jellyfin para Películas.
- [x] **Ensayo de migración con descargas reales, reversible en copia**:
  `0012 → 0013 → 0012` sobre SQLite completa y verificada
  actual (2 descargas, 7 solicitudes, 69 resultados),
  sin activar organización histórica ni alterar prod,
  FK/integridad y recuentos preservados.
  Informe:
  [AVANCE-VERIFICACION-Y-PLAN-PUBLICACION-20261121.md](AVANCE-VERIFICACION-Y-PLAN-PUBLICACION-20261121.md).
- [x] **Publicación PUNTUAL de la descarga #2 y carátula reales**:
  después de verificar que qBittorrent conservaba el MKV de
  16.472 GiB, se hizo preflight sobre Windows NTFS con origen,
  destino y ancestros sin reparse, tamaño exacto
  17.686.540.799 bytes, carpeta destino ausente.
  El primer intento `New-Item -ItemType HardLink` falló
  por los corchetes en el origen; solo dejó una carpeta
  temporal vacía que se verificó y retiró. Se sustituyó
  por Win32 `CreateHardLinkW` de rutas literales, se
  ensayó con un vídeo ficticio `[Esp]` bajo Temp
  (PASS) y se publicó únicamente el MKV mediante
  enlace duro NTFS, seguido de `Directory.Move`
  para exponer una carpeta nueva **sin sobrescribir**:
  `C:\VIEWTV\media\Peliculas\Nadie 2 (2025)\Nadie 2 (2025).mkv`.
  **qBittorrent conserva el origen y puede seguir sembrando;
  el acceso directo `.url` NO se publicó**.
  Se solicitó escaneo real Jellyfin `POST /Library/Refresh`
  HTTP 204. Jellyfin reconoció `Nadie 2`, año 2025,
  carátula y sinopsis; la sincronización inmediata de
  VIEWTV registró `Medio` película disponible con
  portada, fondo y sinopsis. Smoke **10/10 PASS**,
  carpeta con exactamente un MKV, 0 temporales huérfanos,
  source/dest exactamente iguales en tamaño.
  Script reproducible para este caso:
  `scripts/viewtv_publicar_nadie2_puntual_20261121.ps1`.
- [x] **Preparación en rama de la primera autoridad Windows 0013**:
  cola restringida por ID y corte histórico, preparación con identidad
  del torrent, lease, diario de reconciliación NTFS y adaptador de servicio
  Windows escritos como candidato; sin instalación ni migración real.
  Pruebas sobre código ficticio, nunca prueba de publicación real.
  Ver [AVANCE-PUBLICADOR-WINDOWS-CANDIDATO-0013-20261121.md](AVANCE-PUBLICADOR-WINDOWS-CANDIDATO-0013-20261121.md).
- [x] **Ensayo del publicador candidato en NTFS de sandbox**:
  creación de enlace duro, Directory.Move, diario, rechazo de
  colisión y recuperación tras perder confirmación sin recopia.
  Se corrigió el desempaquetado de rutas relativas; Windows
  no recibió ninguna orden de publicación sobre medios reales.
  El usuario confirmó que «Nadie 2» se reproduce.
  Informe:
  [AVANCE-REPRODUCCION-Y-PUBLICADOR-BLOQUEO-POLITICA-20261121.md](AVANCE-REPRODUCCION-Y-PUBLICADOR-BLOQUEO-POLITICA-20261121.md).
- [x] **Error 4551 de Smart App Control resuelto por el usuario**:
  el usuario desactivó la protección desde Windows;
  `VerifiedAndReputablePolicyState=0`. El servicio temporal
  ficticio ahora arranca y devuelve `DOCKER_ACCESS_OK`
  desde LocalSystem; se verificó su retirada sin residuos.
  Esta prueba no justifica instalar el broker como LocalSystem.
- [x] **Release 0013 desplegada coordinadamente en API y worker**:
  se verificó la copia SQLite 0012 online y en frío, SHA-256
  y `tar -tzf`; ensayo `0012→0013→0012` en clon íntegro.
  Se detuvieron solo API/worker y se recrearon por separado
  con sus imágenes 0013 (sin rebuild ni arrastrar dependencias).
  SQLite productiva en `0013_cola_organizacion`, API healthy,
  worker activo, smoke read-only **10/10 PASS**; HLS frontend
  y Jellyfin quedaron intactos. Publicación `disabled`,
  organización worker `false`, auto-descargas true después de
  ID 1, verificación true y arranque/envío manual deshabilitados.
  No hay servicio Windows publicador instalado ni segunda película
  publicada automáticamente. Ver
  [AVANCE-RELEASE-0013-SIN-PUBLICACION-20261121.md](AVANCE-RELEASE-0013-SIN-PUBLICACION-20261121.md).
- [x] **Preflight de la próxima película, antes de solicitar nueva
  descarga:** NTFS sin redirecciones, API/worker 0013, CLI bloqueada,
  auto-descarga/verificación conservadas y publicador no iniciado.
  PowerShell `LISTO_PARA_NUEVA_SELECCION_VIEWTV_0013=SI`;
  SQLite solo lectura `DESCARGAS_NUEVAS=0` en ID > 2.
  **El usuario ya puede buscar/seleccionar otra película autorizada
  desde ViewTV; la publicación sigue desactivada** hasta conocer
  la ID real y verificar la descarga. No añadir torrent manual.
  Informe:
  [AVANCE-PREFLIGHT-NUEVA-PELICULA-0013-20261121.md](AVANCE-PREFLIGHT-NUEVA-PELICULA-0013-20261121.md).
- [x] **Segunda película real (#3) organizada y visible en ViewTV**:
  descarga completada/verificada y propiedad qBittorrent comprobada
  sin escritura. Respaldo SQLite online + `tar.gz` y SHA-256
  verificados; histórico #1/#2 excluido. API autorizada temporalmente
  **solo ID3**, worker sin organización; publicador Windows
  `Once` completó enlace duro NTFS, journal, confirmación de cola
  y solicitud de escaneo Jellyfin. Una coincidencia en Jellyfin
  y una en catálogo ViewTV, ambas con carátula. API devuelta
  a publicación `disabled`, worker intacto; smoke **10/10 PASS**.
  Publicación supervisada, **todavía no servicio automático para
  películas futuras** ni reproducción visual probada de #3.
  Informe:
  [AVANCE-SEGUNDA-PELICULA-ID3-PUBLICACION-20261122.md](AVANCE-SEGUNDA-PELICULA-ID3-PUBLICACION-20261122.md).
- [x] **Reproducción HLS de segunda película #3: corrección técnica desplegada**:
  se detectó que Jellyfin incrustaba subtítulos ASS durante la
  transcodificación. La nueva API 0013 renegocia una fuente HLS
  única con `MediaSourceId` y `SubtitleStreamIndex=-1`, solo cuando
  detecta incrustación. Backend **892/892 PASS**, ruff PASS,
  negociación de ambos filmes sin subtítulos incrustados;
  proxy HLS devuelve HTTP 200 para master, variante y primer
  segmento real. Smoke **10/10 PASS**, sin modificar frontend,
  worker, Jellyfin, archivos ni SQLite. **Falta la prueba visual
  y de sonido del usuario para la película #3**. Publicación
  general permanece desactivada. Informe:
  [AVANCE-REPRODUCCION-SEGUNDA-PELICULA-HLS-0013-20261122.md](AVANCE-REPRODUCCION-SEGUNDA-PELICULA-HLS-0013-20261122.md).
- [x] **Tarea Windows de publicación futura configurada y activa**:
  Task Scheduler ejecuta el publicador en la sesión del usuario
  **sin elevar permisos** (no servicio LocalSystem), al iniciar
  sesión y cada 5 minutos. Política host/API coherentes en
  `general`, `after_id=3`, excluyendo #1/#2/#3; worker sin
  permiso de organización y volúmenes API/worker `/media:ro`.
  Cada pasada controla la cola y sincroniza el catálogo Jellyfin
  transaccionalmente. Se arreglaron dos fallos detectados en pruebas:
  parámetro `$Mode` sobrescrito y `File.Replace` no permitido
  bajo token limitado. **Dos pasadas consecutivas PASS** tras
  corregir, ambas `sin_trabajos` + `catalogo_sincronizado`.
  Backend **896/896 PASS**, smoke **10/10 PASS**, API healthy,
  respaldo SQLite y políticas verificadas. **Se requiere sesión
  Windows iniciada y Docker Desktop disponible**: no es servicio
  previo al login ni cuenta Docker independiente.
  Informe:
  [AVANCE-PUBLICACION-AUTOMATICA-WINDOWS-LIMITADA-0013-20261122.md](AVANCE-PUBLICACION-AUTOMATICA-WINDOWS-LIMITADA-0013-20261122.md).
- [x] **Tercera película real #4 publicada automáticamente**:
  el programador Windows publicó la nueva descarga sin ejecución
  manual y confirmó estado `organizada` con journal/recibo
  Jellyfin. El usuario confirmó que aparecía en la biblioteca,
  inicialmente **sin portada ni ficha enriquecida**.
  Jellyfin ya tenía ambas imágenes, pero el primer sync de ViewTV
  se adelantó a la llegada de los metadatos. Con copia SQLite
  verificada y una sincronización transaccional de catálogo,
  Medio #5 ya tiene título, sinopsis, año, géneros, portada y
  fondo; ambas imágenes responden HTTP 200 desde el proxy.
  El sistema repite `sync` cada 5 minutos, con actualización
  eventual de metadatos posteriores al escaneo. No se tocó el
  vídeo ni se recrearon contenedores. Informe:
  [AVANCE-PELICULA-ID4-METADATOS-Y-CARATULAS-20261122.md](AVANCE-PELICULA-ID4-METADATOS-Y-CARATULAS-20261122.md).
- [ ] **Cierre de prueba E2E para #4**:
  falta que el usuario confirme portada/ficha tras recargar
  ViewTV y que el vídeo **se ve y se oye**; la consulta técnica
  de imágenes no prueba reproducción completa. Mejorar
  experiencia de espera de metadatos solo si sigue suponiendo
  un bloqueo visible.
- [x] **Portada por categorías desplegada**:
  inicio «Explorar» con hero y filas horizontales 2:3;
  primer estante «Recién añadidas» de Jellyfin, y
  categorías TMDB previstas: películas de 2026,
  tendencias, acción, terror, comedia, ciencia ficción
  y series. Fichas, fondos y pósteres sin transferencias
  al explorar; «Descargar» crea una solicitud explícita
  y requiere elegir una fuente. Logo oficial TMDB
  y atribución instalados. **API y frontend HEALTHY
  en producción**, smoke **10/10 PASS**, backend
  **928/928 PASS**, test de biblioteca real solo lectura
  **4 entradas y auth 401/200**. Worker, Jellyfin,
  torrents y SQLite intactos. **TMDB_API_KEY activada**
  posteriormente desde `.env` privado, recargando
  solo la API: las **9 filas** responden con metadatos
  reales y pósteres (4 títulos locales y 8 filas TMDB);
  consulta sin descargas. Código 0 del publicador
  limitado y smoke 10/10 tras recargar la clave.
  Botón «Desinstalar» continúa deshabilitado por
  seguridad hasta liberar correctamente hardlinks
  y origen qBittorrent. Informes:
  [portada](AVANCE-PORTADA-CATEGORIAS-0013-20261122.md)
  y [activación real de TMDB](AVANCE-ACTIVACION-TMDB-CATEGORIAS-0013-20261122.md).
- [ ] **Fase siguiente: catálogo persistente y desinstalación**:
  TMDB ya está conectado, las nueve filas responden
  en producción. Confirmar portada visualmente; después
  diseñar tabla separada de metadatos y actualización
  periódica limitada (sin descargas de vídeo).
  El borrado seguro de copias deberá ser un broker
  aparte con verificación de propiedad, hardlinks y
  quiescencia. No activar borrado de archivos actuales
  por adelantado.
- [x] **Cola 0013 limitada a una sola ID de descarga**:
  `claim_next_organization(..., allowed_download_id=...)` selecciona
  y reserva solo esa ID **dentro de BEGIN IMMEDIATE**; el runner y
  el puente a Jellyfin de laboratorio la respetan. Con dos trabajos
  pendientes solo se organiza y escanea el elegido; el otro no
  consume intentos ni lease. 99 pruebas focales aprobadas.
- [x] **Candidatas de API y worker 0013 construidas**, conservando
  las protecciones actuales de envío/inicio. Alembic `heads` = 0013
  en ambas. Descubierto y corregido un archivo 0008 no legible
  como UID 1000 en las imágenes base. Ensayada migración
  **0012 → 0013 → 0012** en un clon fresco de SQLite productiva,
  preservando integridad, FK, perfiles/medios/solicitudes y el
  respaldo original sin cambios. Compose candidato validado,
  permisos de torrents y organización desactivados. **No se
  desplegó ni migró la base real.**
  Ver
  [AVANCE-ORGANIZACION-UNICA-Y-CANDIDATA-0013-20261120.md](AVANCE-ORGANIZACION-UNICA-Y-CANDIDATA-0013-20261120.md).
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

- [x] **Ensayo de migración/reversión de SQLite 0012/0013**
  con copia actual consistente y ambas imágenes candidatas,
  sin pérdidas de datos ni columnas residuales. No supone
  autorización de migrar la SQLite de producción.
- [ ] Respaldos consistentes de SQLite y configuración
  **inmediatamente antes del despliegue real**, comprobados.
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
  operaciones originales; hoy tiene validación adicional de
  coincidencia. El usuario llegó a seleccionar erróneamente
  un episodio y la corrección está desplegada; debe deshacer
  esa selección desde la UI. No se ha iniciado ningún torrent.
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
  La cola de organización ya filtra una única ID. Hay candidatas
  API y worker 0013 construidas y migración reversible ensayada
  sobre una copia fresca, **no desplegadas**. En producción el
  worker **no ejecuta organización ni solicita escaneos por
  esta ruta**.
- PR #2 sigue en borrador; no significa que 0013 esté desplegado.
- El usuario **sí ha confirmado** acceso a VIEWTV y reproducción
  de vídeos satisfactoria. No se ha verificado por separado
  la operación de cierre de sesión.
- **NO verificados aún:** una elección de contenido correcto
  desde la PWA tras deshacer la errónea, alta/inicio real de
  un torrent autorizado, progreso, verificación y organización.
  La solicitud #3 llegó a ofrecer 62 registros, pero solo
  **2 coincidencias conservadoras** para el título original.
  El usuario eligió antes un capítulo de otra serie, ahora
  bloqueado por API y worker. El estado administrativo del
  proveedor sigue sin verificarse; no se ha realizado descarga.
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
