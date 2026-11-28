# VIEWTV — backlog aplazado tras el primer circuito funcional

**Regla:** no reabrir estas tareas sin una instrucción expresa del usuario; primero completar búsqueda → selección → descarga real → seguimiento → organización → Jellyfin.

**Estado tras release 0013 (21/11/2026):** API, worker y SQLite
ya están en 0013 con publicación desactivada y smoke 10/10.
Poner en marcha el broker Windows **limitado a una nueva ID real**
y verificar una segunda película hasta Jellyfin/reproducción
**no es backlog**, sino el bloqueo prioritario del plan de salida.
La validación de LocalSystem no demuestra permisos confinados ni
autoriza instalar automáticamente el servicio.
El preflight Windows 0013 permitió seleccionar la segunda película
con publicación deshabilitada; esa ID real ya se obtuvo y publicó
en la prueba `single` supervisada. Ver
[AVANCE-PREFLIGHT-NUEVA-PELICULA-0013-20261121.md](AVANCE-PREFLIGHT-NUEVA-PELICULA-0013-20261121.md).

**Hito 22/11/2026:** descarga #3 publicada por el broker
Windows con `-Mode Once` limitado a ID3: origen NTFS
intacto, enlace duro verificado, SQLite `organizada`,
Jellyfin y ViewTV con la película y carátula.
API devuelta a publicación `disabled`, sin Windows Service
permanente. La **automatización desatendida de futuras películas**
sigue siendo objetivo prioritario, **no backlog**; no confundir
éxito individual con automatización general. Informe:
[AVANCE-SEGUNDA-PELICULA-ID3-PUBLICACION-20261122.md](AVANCE-SEGUNDA-PELICULA-ID3-PUBLICACION-20261122.md).

**Reproducción 22/11/2026:** corrección de arranque HLS de #3
por subtítulos ASS incrustados, desplegada únicamente en API 0013;
892/892 pruebas backend, master/variante/primer fragmento 200,
y smoke 10/10. La reproducción visual y sonido deben
confirmarse por el usuario. Publicador permanente y sincronización
sin intervención siguen pendientes prioritarios, no cosmética.
Ver [AVANCE-REPRODUCCION-SEGUNDA-PELICULA-HLS-0013-20261122.md](AVANCE-REPRODUCCION-SEGUNDA-PELICULA-HLS-0013-20261122.md).

**Estado actual 22/11/2026 (supersede anteriores):**
tarea de publicación Windows **ACTIVA** bajo usuario
interactivo limitado, al logon y cada cinco minutos;
solo ID **>3**, API/host `general` aprobado y worker
sin organización. Dos pasadas seguidas `sin_trabajos` con
sincronización de catálogo y código 0; **896/896 tests**.
La próxima prioridad **no es backlog**: validación de una
tercera película real hasta carátula y reproducción automática.
No se ha probado todavía la publicación de una ID #4.
Dependencia: sesión Windows abierta y Docker Desktop.
El aislamiento de identidad Docker y ejecución anterior al login
siguen como posibles mejoras futuras no validadas.
Ver [AVANCE-PUBLICACION-AUTOMATICA-WINDOWS-LIMITADA-0013-20261122.md](AVANCE-PUBLICACION-AUTOMATICA-WINDOWS-LIMITADA-0013-20261122.md).

**Seguimiento 22/11/2026 01:10 — descarga real #4:**
publicador Windows periódico actuó sin intervención,
SQLite #4 `completada`/`verificada`/`organizada`;
el usuario confirmó presencia en biblioteca, pero
sin carátula inicial. Se verificó que Jellyfin ya tenía
portada y fondo mientras ViewTV conservaba metadatos
sin enriquecer. Copia SQLite online consistente antes de
un `sync` transaccional; después la ficha ViewTV tiene
título coincidente, sinopsis, año, géneros, portada y
fondo, ambos accesibles por proxy HTTP 200.
La repetición automática de `sync` cada cinco minutos
permite convergencia sin reinicios. **Pendiente confirmar
visualización de la carátula y reproducción de #4 con
el usuario**, no declarar E2E cerrado todavía.
Ver [AVANCE-PELICULA-ID4-METADATOS-Y-CARATULAS-20261122.md](AVANCE-PELICULA-ID4-METADATOS-Y-CARATULAS-20261122.md).

**Portada Netflix 22/11/2026 — desplegada:**
API y PWA candidatas activadas solo en `api` y
`frontend`, ambos healthy, 10/10 smoke, 928 pruebas
backend. Tras login aparece «Explorar» con hero,
pósteres verticales y filas de recién añadidas
(**cuatro medios locales reales**), películas de
2026, tendencias, acción, terror, comedia, ciencia
ficción y series, con navegación para TV. Consultar
no descarga vídeo; solicitar aún exige elegir fuente.
TMDB tiene logo oficial/atribución y ya está
**TMDB_CONFIGURADA=True** tras recargar únicamente
la API con la clave v3 privada del usuario.
Prueba real de **9/9 filas** por HTTP 200:
recientes (4 con póster), estrenos 2026, tendencias,
acción, terror, comedia, ciencia ficción y series
(todas con fichas y carátulas). Tarea Windows
reanudada con código 0 y smoke 10/10.
**Persistencia programada ya desplegada**:
  catálogo SQLite separado, servicio `catalogador`
  sin privilegios ni montajes de medios, cada seis
  horas agrega fichas únicas con cursores por fuente,
  máximo 50.000. Primera pasada **728 títulos
  únicos** (599 películas + 129 series), 48
  consultas a TMDB. Paginación real de 20 en 20
  y contador en la portada. Suite backend
  **940/940 PASS**, producción smoke 10/10.
  Pendiente: comprobación visual del propietario.
  Informes:
[AVANCE-ACTIVACION-TMDB-CATEGORIAS-0013-20261122.md](AVANCE-ACTIVACION-TMDB-CATEGORIAS-0013-20261122.md)
y [AVANCE-CATALOGO-AMPLIO-PERSISTENTE-0013-20261122.md](AVANCE-CATALOGO-AMPLIO-PERSISTENTE-0013-20261122.md).
**Desinstalar no activo**: requiere
un borrado selectivo seguro de la copia propietaria
y verificación de hardlinks/qBit antes de liberar
espacio, no borrar descargas ajenas. PR #2 sigue
OPEN/DRAFT. Informe completo:
[AVANCE-PORTADA-CATEGORIAS-0013-20261122.md](AVANCE-PORTADA-CATEGORIAS-0013-20261122.md).

- Enlaces HTTP 404 de resultados de Jackett: diagnosticar y corregir solo si impiden obtener una descarga válida para el circuito principal.
- Estado administrativo y fiabilidad del indexador configurado en Jackett: revisión aplazada salvo bloqueo demostrado de búsqueda/descarga.
- Pruebas específicas del cierre de sesión, una vez que el circuito completo sea utilizable.
- Pulido cosmético de estilos, textos, iconografía y animaciones no bloqueantes.
- Mejoras de rendimiento y optimizaciones sin efecto en la reproducción de una película.
- Casuística rara de errores que no impida búsqueda, descarga, organización, integridad o reproducción.
- Endurecimiento adicional del sandbox: TOCTOU residual, quiescencia definitiva y tratamiento ampliado de descriptores abiertos.
- Identidades Windows independientes, aislamiento extra de cuentas y ACL adicionales no indispensables para un único ensayo autorizado.
- Más escenarios del broker, tuberías, firmas, reintentos y fallos físicos que no bloqueen la publicación inicial controlada.
- Automatizaciones, funciones complementarias y cualquier mejora oportunista no imprescindible para terminar la aplicación.


**Actualización de escala (22/11/2026, noche):**
se eliminó el tope fijo de 50.000 fichas de la
implementación anterior. ViewTV ahora admite por
defecto **250.000 fichas únicas**, ampliables por
`VIEWTV_CATALOG_MAX_ITEMS` hasta 1.000.000,
sin ampliar las carpetas de vídeo. El catalogador
revisa más géneros/años con presupuesto máximo
96 solicitudes cada seis horas; las fichas
caducan a los 150 días y se depuran solo en el
volumen de metadatos. Se añadió índice por fecha,
sin cambiar Alembic ni SQLite principal.
Informe:
[AVANCE-CATALOGO-ESCALABLE-250K-20261122.md](AVANCE-CATALOGO-ESCALABLE-250K-20261122.md).
Siguiente mejora de escala: estudiar Daily ID Exports
oficiales para crecer con menos peticiones en lugar
de aumentar indefinidamente `/discover`.


**Series por temporadas/episodios (22/11/2026):** desplegada una ficha única por serie con selector de temporadas y especiales, lista de episodios, miniaturas, sinopsis, estrenos y solicitud explícita SxxEyy; nunca se descarga al navegar. El servidor contrasta serie y temporada con TMDB, rechaza episodios futuros y valida código exacto al emparejar fuentes, sin aceptar varios capítulos en un único resultado ambiguo. Pruebas backend **970/970**, smoke de producción **10/10** y consulta real de serie y temporada HTTP 200. **Pendiente crítico:** `worker/organization_windows_authority.py` solo autoriza publicar películas en el NTFS real, no episodios; no ampliar sin ensayo de broker en sandbox, verificación de contenido real del torrent y propiedad/hardlinks. También pendiente inventario y reproducción por episodio local. Informe [AVANCE-SERIES-TEMPORADAS-EPISODIOS-0013-20261122.md](AVANCE-SERIES-TEMPORADAS-EPISODIOS-0013-20261122.md).


**Jackett + televisión con actualización compartida (22/11/2026):**
Jackett muestra **3 indexadores configurados**, tanto desde
API como worker: `divxtotal`, `dontorrent`,
`mejortorrent`. Las consultas `t=caps` de los tres
devuelven búsqueda de películas y series; sin búsquedas
reales ni transferencias. Se ha desplegado el frontend
`viewtv-frontend:tv-auto-update-0013`, con hash de
versión generado durante Docker build, endpoint sin caché
`/api/app-version`, comprobación cada minuto, aviso
«Actualizar ahora» y recarga automática al quedar
inactivo 90 segundos sin vídeo ni fichas abiertas.
TypeScript/ESLint, build y smoke 10/10 PASS.

**Acceso TV pendiente de paso manual del propietario**:
Windows solo escucha `127.0.0.1:3000`. Para su Wi-Fi
privada `192.168.1.138/24` se necesita habilitar
un portproxy y regla firewall de red privada
restringida; el conector remoto bloquea `netsh`
y no lo ha modificado. No afirmar test en TV hasta
verificación desde el dispositivo.
Documento:
[AVANCE-TV-JACKETT-ACTUALIZACIONES-0013-20261122.md](AVANCE-TV-JACKETT-ACTUALIZACIONES-0013-20261122.md).


**Cohesión carátulas TMDB ↔ Jackett y compatibilidad Samsung (22/11/2026):**
las solicitudes ahora buscan el título local, original y
variantes oficiales enlazadas a un único ID TMDB (máximo
cuatro consultas); se reserva una búsqueda por subtítulo
sin permitir seleccionar películas que solo compartan
una palabra. La API y el worker utilizan los mismos alias,
el año y el código SxxEyy exacto. La clave TMDB se recargó
también en el worker, sin mostrarla. Comprobación real:
«Vengadores: Doomsday» ID TMDB 1003596 y 6 alias;
Jackett devolvió 10 resultados para «Doomsday»,
pero ninguno correspondía a esa película, por lo que
**no se ofreció ningún resultado incorrecto**.
Suite backend **978/978 PASS**, smoke 10/10, sin descargas.

Samsung: se instaló una web alternativa de navegador
`/tv.html` (HTML/JavaScript ES5 sin React) para
perfil/PIN, carátulas, temporadas, biblioteca y prueba
de vídeo HTML5; se mantiene la app moderna.
`http://192.168.1.138:3000/tv.html` devuelve
HTTP 200 y los perfiles por LAN también.
**Pendiente** comprobar realmente en el televisor
inicio de sesión, mando y reproducción/códec;
no inferir éxito solo por HTTP desde Windows.
Documento:
[AVANCE-BUSQUEDA-COHESION-SAMSUNG-0013-20261122.md](AVANCE-BUSQUEDA-COHESION-SAMSUNG-0013-20261122.md).

## Próxima tarea autorizada tras cerrar la cohesión (confirmación del propietario, 22/11/2026)

**Aplicación Samsung instalable, con acabado profesional.**
El propietario confirma que el enlace `/tv.html` **ya funciona en su televisor**,
pero las carátulas se ven en blanco y negro y la interfaz actual le
parece poco cuidada. No dar por comprobadas reproducción ni descarga
en Samsung solo por esta confirmación de arranque.

Objetivo de la siguiente intervención: evaluar el modelo/versión Tizen
y crear una **app instalada desde el televisor, con icono y lanzamiento
tipo Netflix o Prime Video**, reutilizando el servidor doméstico ViewTV
y manteniendo el proxy same-origin; diseñar portada/color/carátulas,
foco/cruceta, carruseles, carga de imágenes y reproducción compatible,
y probarla físicamente sin manipular descargas ni biblioteca.

**Aplazada expresamente:** no empezar diseño visual, empaquetado
Tizen, certificados, publicación en tienda ni nuevas funcionalidades
mientras el bloqueo de cohesión carátula ↔ fuente siga abierto.
No prometer disponibilidad en Samsung Apps/Smart Hub sin comprobar
requisitos específicos de Samsung y el modelo del televisor.

## Idea futura, posterior a la app Samsung: «VIEWTV Momentos» (22/11/2026)

**Propuesta del propietario, documentada pero NO implementada:** feed de
**clips de películas en formato vertical 9:16**, inspirado en el
desplazamiento de TikTok pero adaptado a **pantalla TV 16:9 y mando
↑/↓/OK/Volver**. Un espectador descubre una escena interesante y,
al pulsar OK, abre **la ficha de esa película exacta por TMDB ID**,
con reproducción desde Jellyfin solo si está autorizada y disponible.

La propuesta abarca carátulas a color, foco y controles remotos claros,
vídeo centrado sin deformación, subtítulos, avisos de spoilers y edad,
fuentes de clips **con derechos válidos**, consumo moderado de recursos
y fallback visual si no hay vídeo autorizado. No implica recortar ni
redistribuir películas ajenas sin permiso; **nunca** crea descargas
automáticas para producir clips.

**Orden estricto:** primero completar y validar la **app Samsung instalable
y profesional** ya anotada; después diseñar prototipo con contenido
ficticio y un piloto de clips licenciados, y solo entonces plantear
catálogo y recomendaciones. No hacer cambios de código ahora.

Documento de producto, arquitectura candidata, criterios de aceptación
y riesgos: [IDEA-FUTURA-MOMENTOS-VERTICALES-TV-20261122.md](IDEA-FUTURA-MOMENTOS-VERTICALES-TV-20261122.md).

## Prioridad actual corregida por el propietario: espacio ANTES de Samsung (22/11/2026)

**Tarea en curso: gestión de almacenamiento.** La app Samsung instalable
y su rediseño a color **quedan después** del sistema completo de
espacio, caché y borrado seguro de películas vistas; «VIEWTV Momentos»
queda después de la app. Este orden reemplaza los apartados anteriores
que indicaban la app como próxima tarea inmediata.

**Hito 0015 desplegado:** nueva pantalla «Espacio» en la PWA
principal, disco libre, tamaños lógicos de biblioteca/descargas,
caché 0 GiB actualmente, cuota de 80 GiB indicada como **no aplicada**;
marcas «vista» por perfil, solicitudes de retirada confirmadas y
cancelables. La solicitud **no borra la película** ni libera espacio.
Limpiar caché se limita a temporales propios marcados y no a Jellyfin,
torrent, originales NTFS ni base de fichas TMDB. Backend
**1017/1017 pruebas**, frontend **18/18**, smoke **10/10**,
API/worker/frontend saludables, SQLite 0015; documentos, código y
rollback preparados. Ningún archivo de película o torrent fue eliminado.

**Bloqueo prioritario aún abierto (antes de la app):** implementar y
validar la **retirada física segura** mediante la autoridad Windows,
resolviendo propiedad exacta Jellyfin↔journal↔descarga, todos los
hardlinks, torrents ajenos/en curso y acceso de otros perfiles. Requerir
confirmación de administrador de biblioteca, pruebas de sandbox NTFS
y medición de bytes *realmente* liberados. No utilizar `os.remove`
desde API ni borrados por coincidencia de nombres; con el flujo actual,
24,31 GiB en `Peliculas` y 24,31 GiB en
`descargas_temporales` pueden representar datos compartidos.
Pendiente también aplicar cuota real solo a cachés escritoras de
VIEWTV que se implementen en el futuro. No afirmar borrado terminado.

Informe completo:
[AVANCE-GESTION-ESPACIO-CACHE-0015-20261122.md](AVANCE-GESTION-ESPACIO-CACHE-0015-20261122.md).

## Gestión de espacio 0016: prueba real de retirada y bloqueo (22/11/2026)

**Se mantiene como tarea prioritaria anterior a Samsung.**
Informe:
[AVANCE-AUDITORIA-RETIRADA-SEGURA-0016-20261122.md](AVANCE-AUDITORIA-RETIRADA-SEGURA-0016-20261122.md).

- [x] **Corregido bloqueo real del publicador Windows** tras
  Alembic 0014/0015: `organization_windows_cli` reconoce revisiones
  0013/0014/0015 si el contrato de columnas está intacto, y rechaza
  otras. API actualizada **solo ella** a
  `viewtv:publicador-compatible-api-0016`. Estado `listo`,
  preflight Windows **PASS**, smoke **10/10 PASS**.
- [x] Auditoría Windows real, **sin escritura**: dos diarios
  y hardlinks NTFS válidos con hashes de manifiesto correctos;
  **una carpeta de películas no tiene diario verificable** y queda
  excluida; un diario pertenece al histórico ≤3.
- [x] Cruce exacto Jellyfin por ID y ruta, no nombre:
  **dos** rutas de películas corresponden sin ambigüedad a los
  vídeos de esos dos diarios. Los registros antiguos no tienen
  enlace directo único en SQLite con `medio.id`.
- [x] qBittorrent solo GET: ambos torrents organizados pertenecen
  a ViewTV, pero **los dos estaban en uso y ninguno detenido** al
  comprobarlo. La regla de seguridad rechaza torrentes activos,
  ajenos o ambiguos y exige autorización posterior.
- [x] Sandbox Windows separado con enlace NTFS ficticio: se
  rechazó inspección durante bloqueo de archivo y se probó
  borrar **solo la copia ficticia**, conservando su origen;
  cero películas/torrents reales tocados.
- [ ] **Bloqueo antes de la app:** construir autoridad Windows
  de retirada bajo autorización específica del administrador,
  vinculando los tres orígenes en un preflight único, deteniendo
  primero solo torrents propios autorizados, excluyendo reproducciones,
  otros enlaces/perfiles y cambios concurrentes. Probar
  recuperación tras fallo y contabilizar **bytes físicos** liberados.
  No interpretar un clic en «vista» como permiso de borrar ni
  llamar «eliminado» a una solicitud pendiente.
- [ ] Gestionar efectivamente cuota de caché propia cuando existan
  escritores de temporales; no tocar caché Jellyfin.

**No se activó ningún endpoint ni tarea que borre películas**.
El botón actual sigue siendo «Solicitar retirada» hasta que se
demuestre el circuito completo. Mantener PR #2 OPEN/DRAFT.

## Cierre de jornada — 22/11/2026

**Sesión detenida a las 23:19 (Madrid).** Resumen completo del
estado desplegado, pruebas, límites de borrado, respaldos y primer
trabajo para el lunes 23 de noviembre en
[CIERRE-JORNADA-VIEWTV-20261122.md](CIERRE-JORNADA-VIEWTV-20261122.md).
No iniciar la app Samsung antes de cerrar la gestión de almacenamiento.

## Gestión de espacio 0017: caché propia con cuota (26/11/2026)

**Hito probado y desplegado en la instalación actual.**
Informe: [AVANCE-CACHE-PRIVADA-CUOTA-0017-20261126.md](AVANCE-CACHE-PRIVADA-CUOTA-0017-20261126.md).

- [x] Separar los temporales nuevos en **volumen Docker exclusivo de la API**
  `viewtv_cache_propia_0017`, distinto de `/cache` en NTFS y de `/media`.
  El volumen empieza vacío; no se tocaron medios/torrents ni la caché
  heredada, Jellyfin o TMDB.
- [x] Implementar escritor interno con límite de 80 GiB por defecto
  **solo para los temporales que pasen por él**, límite por objeto
  de 16 MiB, caducidad de 14 días y evicción de antiguos si falta cuota.
  `flock` serializa inicio y borrado entre procesos.
- [x] Validación de marcador, permisos, UID, inodo, enlace único y
  nombre cerrado; se **bloquea** ante archivo no reconocido,
  enlace simbólico o hardlink ajeno. Pruebas ficticias de
  concurrencia y pérdida de confianza.
- [x] Panel `Espacio` ampliado con tamaño de caché privada,
  cuota parcial y botón `Vaciar caché privada` condicionado.
  API con 401 sin sesión y confirmación exacta.
- [x] **1054/1054 backend**, **18/18 frontend**, TypeScript,
  ESLint, Ruff y build de producción; smoke posterior **10/10**;
  API/frontend nuevas **healthy**, worker y Jellyfin sin recrear.
  SQLite y preflight del publicador Windows intactos.
- [x] Reversión de imágenes comprobada en preflight, sin ejecutarla
  ni borrar el volumen.
- [ ] **Pendiente real de caché:** integrar solo escritores de
  temporales de ViewTV con la nueva función `guardar_temporal`
  cuando se creen; no afirmar cuota global o espacio liberado
  actualmente. La caché privada sigue vacía.
- [ ] **Prioridad principal aún abierta antes de la app:** retirada
  física por película con **autorización diferenciada de
  administrador**, verificación conjunta de Jellyfin/diario
  Windows/hardlinks/qBittorrent, exclusión de streams y
  torrents en uso, fases recuperables y medición de bytes
  realmente liberados. No activar borrado real ni detener
  torrents basándose en un PIN de perfil o en que esté vista.

Después de esta tarea de almacenamiento: app Samsung instalable;
después, «VIEWTV Momentos». Mantener PR #2 **OPEN/DRAFT**.

## Retirada segura de películas — preflight unificado 0018 (26/11/2026)

Informe verificable:
[AVANCE-PREFLIGHT-UNIFICADO-RETIRADA-0018-20261126.md](AVANCE-PREFLIGHT-UNIFICADO-RETIRADA-0018-20261126.md).

- [x] Implementar decisión **solo lectura** de SQLite,
  marcas de «vista» y solicitudes pendientes por perfil,
  ID/ruta Jellyfin, diario Windows, dos hardlinks NTFS,
  estado/archivos qBittorrent y aislamiento de descargas.
  Correlación por `descarga.id`, huella del diario y ruta exacta,
  sin confiar en títulos como permiso.
- [x] Auditar la biblioteca real sin escritura: **4 películas
  revisadas, 2 publicaciones NTFS válidas, 4 retiradas bloqueadas,
  2 torrents activos/incompletos, cero solicitudes pendientes,
  cero marcas de visto y cero borrados**. No asumir que los
  archivos extra/no verificables de qBit puedan borrarse.
- [x] Exigir perfiles activos completamente marcados como «vista»
  y petición pendiente válida **además** de permiso específico
  de administrador aún no implementado. Ante fuentes ausentes,
  versiones ambiguas o huellas diferentes, bloquear y no
  liberar ningún archivo.
- [x] Ensayo NTFS **100 % ficticio** en Windows:
  lector abierto y tercer hardlink bloqueados, interrupción
  recuperable y retirada de ambas referencias del mismo archivo
  en directorio GUID privado; producción no modificada.
- [x] Pruebas de identidad y denegación 0018 **55/55 PASS**,
  Ruff PASS; suite backend completa **1109/1109 PASS**.
  Diagnóstico qBit GET: 6 archivos, pero solo 2 incluidos
  en diarios de publicación, **4 archivos extra a proteger**;
  ningún torrent fue manipulado.
- [ ] **PRÓXIMO ANTES DE SAMSUNG:** autoridad independiente
  del administrador, consentimiento explícito por película,
  reserva atómica frente al publicador y qBit, protección
  de reproducciones de Jellyfin y enlaces ajenos, journal
  durable con pruebas de interrupción real, ejecutor Windows
  limitado a un ID y medición física del espacio recuperado.
  **No ejecutar borrados reales** sin película concreta
  autorizada y todas las comprobaciones positivas.
- [ ] Cache 0017: integrar escritores reales propios cuando
  existan y conservar el límite solo para ese volumen; no
  confundirlo con cuota global de caché.
- [ ] App Samsung instalable y después «VIEWTV Momentos».

El preflight 0018 es un **script local manual de solo lectura**;
no se añade un endpoint destructivo ni se altera el despliegue
de API/frontend 0017. PR #2 se mantiene OPEN/DRAFT.

## Gestión de espacio 0019 — autorización separada de administrador (26/11/2026)

Informe: [AVANCE-AUTORIZACION-ADMINISTRADOR-RETIRADA-0019-20261126.md](AVANCE-AUTORIZACION-ADMINISTRADOR-RETIRADA-0019-20261126.md).

- [x] Contrato de aprobación **offline** por película y descarga exactas,
  distinto del PIN del perfil y de la autenticación web: HMAC-SHA256,
  nonce de 128 bits, vencimiento a 10 minutos, confirmación explícita
  del ID, validación de cambios de evidencia y registro de consumo único
  en SQLite **de sandbox**.
- [x] Requerir que el preflight 0018 no tenga más bloqueos que falta de
  autorización administrativa antes de siquiera preparar un desafío.
  La firma no concede autorización de borrado físico por sí sola.
- [x] Pruebas sintéticas de falsificación de firma, caducidad,
  identidad de película/descarga, cambio de pruebas, permisos de
  secreto/diario, symlinks y 16 consumos concurrentes.
  **94/94 pruebas específicas, 1148/1148 suite backend PASS**,
  Ruff y smoke de solo lectura **10/10 PASS**.
- [x] Verificación real read-only: **4 películas, 0 candidatas**,
  **0 aprobaciones emitidas, 0 archivos y 0 torrents modificados**.
  Los cuatro archivos qBit sin publicación acreditada continúan
  protegidos; dos torrents siguen activos en la última lectura.
- [ ] **Pendiente prioritario:** identidad de administrador real
  custodiada fuera de API y navegador, alta y revocación segura,
  comprobación atómica y locking Windows/qBit/Jellyfin,
  diario durable, recuperación tras apagón, medición de espacio
  realmente liberado y pruebas de sandbox antes de permitir
  retiro real de una sola película específicamente aprobada.
- [ ] Caché: conectar escritor real que use el volumen privado 0017.
- [ ] Solo al cerrar la gestión de espacio: app Samsung profesional;
  después ViewTV Momentos.

No se despliega el módulo 0019 en la API ni se crea ninguna clave
administrativa de producción. PR #2 sigue OPEN/DRAFT.

## Gestión de espacio 0020 — inventario qBit y diario NTFS recuperable (26/11/2026)

Informe: [AVANCE-INVENTARIO-QBIT-DIARIO-RETIRADA-0020-20261126.md](AVANCE-INVENTARIO-QBIT-DIARIO-RETIRADA-0020-20261126.md).

- [x] Revisar exclusivamente por GET la totalidad de archivos
  de los dos torrents publicados. Seis archivos: dos coinciden
  con sus diarios; cuatro extras son **metadatos** y suman
  **488 bytes lógicos**, con dos nombres fuera de las reglas
  estrictas de normalización. Mantener los cuatro protegidos.
  No autorizan eliminar ni los originales ni el torrent.
- [x] Motor puro que clasifica inventarios y falla ante tamaños
  diferentes, archivos repetidos, datos incompletos o rutas
  inesperadas, sin crear nunca planes de borrado.
- [x] Windows: ensayo **solo sandbox** con diario write-through,
  un reinicio simulado en proceso PowerShell independiente
  después de retirar un enlace, restauración verificada,
  recuperación **idempotente** y finalización repetible.
  Se retiraron solo los dos enlaces **ficticios**; directorio
  GUID temporal limpiado.
- [x] Pruebas nuevas del inventario **11/11 PASS**, Ruff PASS;
  **suite backend completa 1159/1159 PASS**; smoke de solo lectura
  **10/10 PASS** y auditoría NTFS posterior **2/2 PASS**.
- [ ] Antes de una retirada real: enrolamiento admin,
  autorización concreta de película, examen de los metadatos
  qBit extra, reserva Windows/qBit/Jellyfin, streams inactivos,
  apagones simulados más exhaustivos, journal autenticado
  y medición física real de espacio libre.
- [ ] Actualizar futura caché solo con productores de temporales
  exclusivamente propios. No tocar caché Jellyfin.
- [ ] Primero terminar la liberación segura de espacio;
  **después** app Samsung y luego VIEWTV Momentos.

No se modifica producción en 0020; PR #2 abierto/draft.

## Retirada segura 0021 — sesiones Jellyfin y medición NTFS (27/11/2026)

Informe: [AVANCE-SESIONES-JELLYFIN-MEDICION-NTFS-0021-20261127.md](AVANCE-SESIONES-JELLYFIN-MEDICION-NTFS-0021-20261127.md).

- [x] Crear **guard puro** de sesiones Jellyfin que bloquea películas
  reproduciéndose o pausadas y falla de forma conservadora con ítems
  incompletos, sesiones duplicadas, transcodificación sin identidad
  o consultas inválidas. **Siempre** devuelve
  `habilita_borrado_fisico=false`; no implementa endpoint destructor.
- [x] Dos consultas reales `GET /Sessions` desde API existente,
  ejecutando código 0021 temporalmente en memoria sin cambiar
  imagen/SQLite/servicios. **4 películas consultadas; 0 sesiones
  reportadas**. Es una observación, NO exclusión de nuevos streams
  ni permiso para retirar películas.
- [x] Ensayo **exclusivamente ficticio de 8 MiB** en carpeta GUID
  del TEMP Windows, mismo volumen que medios, con dos hardlinks
  NTFS, Win32 `GetDiskFreeSpaceExW` y recuento nativo de enlaces.
  Delta al retirar primer link **0 bytes** y al retirar último
  **+8 MiB observados**. No atribuir este resultado a ninguna
  película real; el disco puede cambiar por otros procesos.
- [x] **47/47 pruebas específicas de sesiones y privacidad PASS**,
  Ruff PASS; **suite backend 1206/1206 PASS**, smoke 10/10 PASS
  y auditoría posterior de Windows 2/2 diarios válidos.
- [x] Preflight real 0018 sigue con **4/4 películas bloqueadas**,
  dos torrents activos, dos publicaciones verificadas y cero
  archivos reales borrados.
- [ ] **ANTES DE ELIMINAR:** bloquear realmente nuevas
  reproducciones/transcodificaciones y archivos abiertos,
  coordinar publicación Windows y qBit en un lock común,
  resolver los 4 metadatos protegidos, activar identidad
  administrativa separada, unir el diario recuperable a una
  autorización consumida y medir espacio libre antes/después.
  No detener torrents ni borrar películas sin aprobación concreta.
- [ ] Conectar escritores propios a caché privada de 0017, sin
  tocar caché Jellyfin ni originales compartidos.
- [ ] Solo después de gestión segura: app Samsung Tizen instalable;
  finalmente VIEWTV Momentos.

Sin migraciones, despliegues ni cambios en medios de producción en 0021.
PR #2 sigue abierto y en borrador.

## Retirada segura 0022 — mutex Windows compartido (27/11/2026)

Informe: [AVANCE-MUTEX-COMPARTIDO-RETIRADA-0022-20261127.md](AVANCE-MUTEX-COMPARTIDO-RETIRADA-0022-20261127.md).

- [x] Implementar en el código fuente del publicador 0013 una
  exclusión nativa Windows por mutex **Global fijo**, adquirida
  **antes del claim** y mantenida hasta cerrar reconciliación,
  hardlinks, confirmación y escaneo. Liberación segura en
  `finally`; falta de biblioteca o mutex ocupado/abandonado
  impide continuar.
- [x] Auditoría NTFS de retirada **sin borrados** que obtiene
  el mismo mutex y devuelve explícitamente que no coordina
  qBittorrent ni nuevos streams Jellyfin.
- [x] Ensayo en Windows con **dos procesos ficticios**:
  exclusión efectiva, nombre productivo no personalizable,
  recuperación después de finalizar abruptamente solo el
  proceso de sandbox, sin medios tocados.
- [x] Ensayo del propio `Process-One` con mocks: ningún
  claim ni publicación real, retorno `sin_trabajos` y
  bloqueo ante error simulado del broker.
- [x] Tests de regresión **15/15 PASS**, Ruff PASS,
  backend general **1221/1221 PASS**, smoke 10/10 PASS;
  auditoría NTFS 2/2 verificada y preflight 4/4 películas
  bloqueadas sin cambios productivos.
- [ ] **NO SE HA DESPLEGADO EL PUBLICADOR CON NUEVO MUTEX**:
  validar y respaldar el script de servicio Windows,
  programar actualización supervisada tras comprobar que
  no procesa trabajo, mantener un único proceso activo,
  verificar ACL y rollback. La versión vieja NO participa
  en este mutex.
- [ ] El mutex no inmoviliza qBittorrent ni streams Jellyfin.
  Crear reserva/bloqueo efectivamente compartido, revalidación
  atómica, permisos de administrador 0019, journal 0020 y
  medición física 0021. No borrar películas reales sin
  autorización específica por título ni detener torrents.
- [ ] Después de gestión de espacio completa: app Samsung
  instalable; luego VIEWTV Momentos.

No hay migraciones ni cambios de contenedores en el hito 0022.
PR #2 sigue OPEN/DRAFT.

## Gestión de espacio 0023 — auditoría del publicador instalado (27/11/2026)

Informe:
[AVANCE-PREFLIGHT-ACTUALIZACION-PUBLICADOR-0023-20261127.md](AVANCE-PREFLIGHT-ACTUALIZACION-PUBLICADOR-0023-20261127.md).

- [x] **Diagnóstico de instalación real exclusivamente de lectura**:
  tarea periódica `READY` (habilitada), cuenta `Limited`,
  wrapper coincide con fuente, 0 procesos publicadores detectados
  en la instantánea, 0 servicios SCM duplicados; **publicador
  instalado antiguo** y **helper mutex 0022 no instalado**.
  No puede afirmarse exclusión productiva ni quietud durable.
- [x] Barrera local que acepta solo campos conocidos de auditoría
  y **bloquea** ante versiones incompatibles, tarea habilitada,
  fuente ambigua, permisos, servicios/procesos extra o cualquier
  afirmación de operación destructiva. Resultado real:
  **4 motivos de bloqueo; permiso automático de actualizar NO**.
- [x] Ensayo de instalación/recuperación/rollback con fuentes
  reales **copiadas, pero jamás ejecutadas**, dentro de
  directorio TEMP GUID con scripts y mutex ficticios:
  `File.Replace` con backup, interrupción entre script/helper,
  recuperación y rollback por otro proceso, reintentos idempotentes,
  comprobación SHA-256 y limpieza no recursiva.
- [x] **48/48 pruebas específicas** de barrera y runner, Ruff
  PASS, smoke real **10/10 PASS**; backend completo **1269/1269 PASS**.
  No se instalaron nuevos archivos en el publicador activo.
- [ ] **SIGUIENTE:** acordar ventana y aprobación de administrador
  para respaldar y deshabilitar temporalmente la tarea habilitada,
  confirmar que no hay ningún trabajo activo y reemplazar
  script+helper como pareja coherente en el directorio
  protegido. **No realizar la sustitución automáticamente.**
- [ ] El mutex sigue siendo cooperativo: faltan exclusión de
  qBit/Jellyfin, protección de sesiones y archivos abiertos,
  ticket de autorización por película, diario durable de
  retirada y comprobación de bytes realmente liberados.
  Los cuatro metadatos qBit y la carpeta sin diario no se borran.
- [ ] Una vez concluida la seguridad del espacio: Samsung Tizen
  instalable; después VIEWTV Momentos.

No se alteraron el publicador productivo ni las tareas, películas,
SQLite, torrents o servicios del equipo. PR #2 OPEN/DRAFT.

## Gestión de espacio 0024 — solicitud de retirada por película verificada (27/11/2026)

Informe: [AVANCE-REVISION-RETIRADA-SOLICITADA-0024-20261127.md](AVANCE-REVISION-RETIRADA-SOLICITADA-0024-20261127.md).

- [x] Verificar por lectura SQL **la solicitud real de un perfil**,
  tras marcar una película como vista, mediante identidad exacta
  de título/año, sin registrar nombres, IDs de perfiles o rutas
  en la documentación. Estado observado `pendiente_revision`
  con archivo intacto, un perfil aún sin marcar vista y
  **ninguna autorización administrativa**.
- [x] Nueva revisión local read-only que cruza **dos consultas
  SQL** de la película con el snapshot qBit/Jellyfin/SQLite y
  **dos inventarios NTFS Windows**; denegar si cambian las
  solicitudes, marcas, identidad o diarios durante la evaluación.
- [x] Evaluador puro que respeta los perfiles independientes:
  solicitud válida de un perfil no autoriza borrar la biblioteca,
  cancelación implica falta de petición y todos los perfiles
  vistos **tampoco** equivale a autorización admin.
- [x] **43/43 pruebas específicas y Ruff PASS**, smoke de
  solo lectura **10/10 PASS**, backend general **1312/1312 PASS**.
  Sin nuevos endpoints destructivos,
  migraciones ni cambios de servicios/media/torrents.
- [ ] Las **cuatro películas siguen bloqueadas** por preflight:
  no alterar marcas de otros perfiles ni parar torrents para
  superar barreras. Metadatos qBit extras protegidos.
- [ ] Desplegar bajo mantenimiento supervisado la versión del
  publicador Windows con mutex; bloquear realmente la
  concurrencia Jellyfin/qBit, activar autorización administrativa
  independiente por película y journal transaccional durable,
  luego medir bytes físicos realmente recuperados.
- [ ] Solo después: app Samsung Tizen profesional; luego Momentos.

PR #2 continúa abierto/draft. No se ha eliminado ninguna película.

## Gestión de espacio 0025 — doble snapshot integral de retirada (27/11/2026)

Informe: [AVANCE-DOBLE-SNAPSHOT-RETIRADA-0025-20261127.md](AVANCE-DOBLE-SNAPSHOT-RETIRADA-0025-20261127.md).

- [x] Detectada una brecha en el preflight por película 0024:
  solo se comparaban dos lecturas de solicitudes y NTFS,
  pero **una** instantánea de qBit/Jellyfin/descargas SQL.
- [x] Nueva barrera pura 0025 que exige **dos snapshots
  completos idénticos** SQL/Jellyfin/qBit, **dos lecturas
  completas de diarios** Windows y **dos auditorías NTFS**,
  siempre sin permisos de borrado ni bloqueo transaccional.
  Rechaza cambios incluso en otra película durante la consulta.
- [x] Tests sintéticos de cambios de torrent (estado, progreso,
  tags, path, hash), ficheros, ruta Jellyfin, vistas y peticiones,
  fuentes incompletas, diario y NTFS no concordantes.
  **91/91 pruebas combinadas 0024/0025 PASS**, Ruff PASS.
- [x] Consulta read-only de película con retirada pendiente:
  **2 snapshots coincidentes**, 1 solicitud válida,
  1/2 perfiles «vista», torrent activo o incompleto para la
  política, archivos qBit adicionales protegidos y
  **borrado físico NO**. /Sessions Jellyfin 0 reproducciones
  observadas, sin garantizar inactividad posterior.
- [x] Smoke web/API solo lectura **10/10 PASS**;
  backend total **1360/1360 PASS**, dos advertencias externas;
  auditoría NTFS final sin medios borrados.
- [ ] **Importante:** dos lecturas iguales no constituyen una
  reserva atómica. Falta impedir nuevos streams de Jellyfin,
  qBit activo y cambios de publicación Windows antes de
  otorgar una autorización ejecutable por título.
- [ ] El publicador instalado aún no usa mutex 0022; requiere
  mantenimiento supervisado, comprobaciones de servicio,
  respaldo y validación de instalación (0023).
- [ ] Concluir eliminación y medición NTFS por título seguro
  antes de la app Samsung instalable; después Momentos.

No se modificaron perfiles, SQLite, medios, torrents ni
servicios productivos. PR #2 sigue OPEN/DRAFT.

## Seguridad de retirada 0026 — custodia qBit sin pausar torrents (27/11/2026)

Informe: [AVANCE-CUSTODIA-ESTADO-QBIT-0026-20261127.md](AVANCE-CUSTODIA-ESTADO-QBIT-0026-20261127.md).

- [x] Nuevo evaluador puro para verificar cada torrent publicado
  por **hash, etiqueta VIEWTV exclusiva, raíz Windows y diario**,
  sin confundir esa identidad con propiedad de archivos extras.
- [x] Se distingue **reposo reportado + 100 %** de cualquier
  actividad / comprobación / transferencia: en producción,
  **2/2 torrents NO están en reposo**. Pausarlos o detenerlos
  para convertirlos en candidatos está prohibido.
- [x] Recuento completo qBit: **6 archivos, 2 manifiestos
  correlacionados y 4 extras custodiados** (metadatos,
  488 bytes lógicos; 2 nombres no normalizables).
  Ninguno se elimina, excluye o modifica automáticamente.
- [x] Orquestador de solo lectura con **dos instantáneas completas
  SQL/Jellyfin/qBit, dos lecturas de diarios y dos auditorías NTFS**.
  Cualquier cambio detectado exige abortar sin permiso de borrar.
- [x] **64/64 pruebas específicas 0026**, Ruff PASS; smoke
  real de solo lectura **10/10 PASS** y backend **1424/1424 PASS**.
  Los contadores no exponen rutas, perfiles ni hashes.
- [ ] El mutex 0022 **no está en el publicador instalado**:
  falta intervención supervisada 0023, sin detener tarea o
  torrents desde la auditoría.
- [ ] Hace falta exclusión efectiva de nuevos streams Jellyfin,
  de qBit y Windows, protección de extras y aprobación del
  administrador por película antes de retirar hardlinks con
  recuperación durable y medir bytes NTFS liberados.
- [ ] Después de terminar espacio: app Samsung Tizen;
  posteriormente VIEWTV Momentos.

PR #2 OPEN/DRAFT, sin merge. Cero archivos/torrents reales alterados.

## Seguridad de reproducción 0027 — admisión y drenaje, SOLO laboratorio (27/11/2026)

Informe: [AVANCE-ADMISION-REPRODUCCION-0027-20261127.md](AVANCE-ADMISION-REPRODUCCION-0027-20261127.md).

- [x] Identificadas **3 rutas distintas** de reproducción VIEWTV:
  `playback-info`, streaming directo y playlists/segmentos
  HLS. Los tokens HLS vigentes alcanzan **4 horas**;
  negar solo el botón «Reproducir» deja lecturas posibles.
- [x] El puerto Docker publicado de Jellyfin solo aparece
  en loopback `127.0.0.1:8097`, **sin demostrar** ausencia
  de accesos por redes locales de contenedores u otros canales.
- [x] Protocolo **solo para pruebas** de admisión y drenaje por
  película con SQLite privado en TEMP GUID, `BEGIN IMMEDIATE`
  y `synchronous=FULL`: al comenzar drenaje bloquea nuevas
  sesiones y espera a que terminen también los streams en vuelo.
- [x] Concurrencia ensayada con 16 clientes y caída de otro
  proceso: sesiones abandonadas **permanecen bloqueantes**;
  nunca se libera por timeout ni se emite permiso físico.
- [x] **43/43 pruebas específicas 0027 PASS**, Ruff PASS,
  smoke **10/10 PASS** y suite backend **1467/1467 PASS**.
  Auditoría final NTFS de solo lectura, sin borrados.
- [ ] **NO CONECTADO EN PRODUCCIÓN**: controlar todas las
  rutas reales (también cada segmento HLS), ligarlas a
  identidad de sesión/perfil/medio y cerrar el contador
  solo cuando acaba el iterador HTTP. No abrir acceso
  a contenido en retirada.
- [ ] Excluir accesos directos a Jellyfin y escrituras qBit,
  actualizar publicador antiguo bajo mantenimiento supervisado
  y consumir aprobación admin estricta de una sola película,
  con diario NTFS y prueba de espacio liberado.
- [ ] Primero espacio y seguridad; después app Samsung Tizen
  profesional y finalmente VIEWTV Momentos.

Sin cambiar reproducción real, Jellyfin, qBit, perfiles,
tarea programada Windows, SQLite de producción ni películas.
PR #2 continúa OPEN/DRAFT.

## Retirada segura 0028 — barrera ASGI integrada SOLO en TestClient (27/11/2026)

Informe:
[AVANCE-CAPA-ASGI-REPRODUCCION-0028-20261127.md](AVANCE-CAPA-ASGI-REPRODUCCION-0028-20261127.md).

- [x] Implementado en **archivo nuevo, NO registrado en
  `app.main`**, el wrapper ASGI que deniega las tres rutas
  reales de reproducción durante drenaje: `playback-info`,
  `stream`, y todas las playlists/fragmentos HLS en `hls`.
  Incluye tokens HLS firmados antes del comienzo del drenaje.
- [x] Antes de cada handler abre un registro en la SQLite
  TEMP GUID del laboratorio 0027 y lo conserva hasta el
  `finally` que cubre también streaming/cancelación.
  Rechaza rutas no canónicas, futuras rutas de medios sin
  inventario y peticiones cuando la DB no es confiable.
- [x] Ensayo real **FastAPI TestClient** sobre las rutas
  productivas, pero con base en memoria y fuente Jellyfin
  ficticias, demuestra 423 **antes de contactar con Jellyfin**.
  Nunca se accede a la SQLite ni a los medios productivos.
- [x] Pruebas de streaming en vuelo, cancelación y aislamiento
  entre películas; **23/23 tests específicos PASS**,
  Ruff PASS, smoke web/API **10/10 PASS** y suite backend
  completa **1490/1490 PASS**. Auditoría NTFS 2/2 sin borrados.
- [ ] **PROHIBIDO DESPLEGAR ESTE WRAPPER**: todavía actúa
  antes de autenticar el perfil, podría revelar por 423
  el estado de drenaje a un cliente anónimo y no liga
  capacidades HLS a una sesión durable autenticada.
- [ ] Integrar autenticación y duración efectiva de streams
  en las rutas, limitar clientes Jellyfin externos y
  accesos NTFS/qBit ajenos. La barrera 0028 solo protege
  las peticiones que atraviesan el wrapper en pruebas.
- [ ] Publicador Windows instalado necesita upgrade
  supervisado 0023; permiso por película 0019 y preflight
  de todos los perfiles/archivos, journal de retirada
  durable y medición física de bloques aún pendientes.
- [ ] Terminar espacio seguro antes de Samsung Tizen;
  luego VIEWTV Momentos.

Sin detener procesos, cambiar API/frontend productivos ni
eliminar películas o torrents. PR #2 OPEN/DRAFT.

## Retirada 0029 — autenticar perfiles ANTES de consultar drenaje (27/11/2026)

Informe: [AVANCE-AUTENTICACION-DRENAJE-0029-20261127.md](AVANCE-AUTENTICACION-DRENAJE-0029-20261127.md).

- [x] Laboratorio HTTP 0029 llama a `get_current_profile` real,
  con JWT, cookie y SQLite **en memoria** antes de consultar
  estado de retirada. Sin sesión, JWT caducado/falso o perfil
  inactivo devuelve siempre 401, incluso en drenaje.
- [x] Una nueva tabla TEMP registra el propietario **perfil + medio**
  de cada sesión en la misma transacción SQLite; otro perfil
  no puede consumir ni terminar las lecturas ajenas.
- [x] TestClient sobre negociación, stream directo, playlist y
  segmentos HLS con Jellyfin ficticio; 423 tras autenticación,
  sin llamar upstream. **38/38 pruebas PASS**, Ruff PASS,
  backend **1528/1528 PASS**, smoke real **10/10 PASS**.
- [x] Comprobado explícitamente que los HLS firmados actuales
  **son transferibles entre perfiles autenticados**: falta
  firmar identidad y generación de sesión y revocar tokens
  previos antes de poder desplegar este protocolo.
- [ ] **No desplegado**: resolver HLS por perfil y sesión,
  aislar accesos directos Jellyfin, qBit y lectores NTFS,
  actualizar publicador con mutex de modo supervisado y
  obtener aprobación administrativa por película.
- [ ] Tras liberación física segura de espacio, app Tizen Samsung
  instalable y después VIEWTV Momentos.

PR #2 sigue OPEN/DRAFT. Sin cambiar medios, torrents, perfiles ni servicios.

## 0030 — Actualización supervisada Windows (27/11/2026)

**Despliegue Windows realizado y verificado**: nueva versión 0022 del publicador y helper instalados con File.Replace, copia privada SHA-256 verificada, tarea deshabilitada y quietud comprobada dos veces; rollback probado en proceso independiente (sandbox), preflight real instalado correcto y tarea reactivada Limited/Interactive. Pasada `Once` real: resultado 0, `sin_trabajos`, catálogo sincronizado; sin servicio permanente. Auditoría posterior: **2/2 diarios NTFS verificados**, **4/4 películas bloqueadas**, 0 retiradas, 0 torrents modificados. Conservados los cuatro metadatos de qBit, carpeta sin diario y cachés originales. Informe: [AVANCE-ACTUALIZACION-SUPERVISADA-PUBLICADOR-0030-20261127.md](AVANCE-ACTUALIZACION-SUPERVISADA-PUBLICADOR-0030-20261127.md).

**Reserva de calidad abierta:** suite backend 1528/1528, TypeScript, ESLint y smoke 10/10 aprobados; Ruff de los módulos del gate de actualización 0023 limpio. La comprobación Ruff global sobre `backend worker scripts` **todavía falla por hallazgos heredados fuera de 0030**. No se declara el repositorio completamente verde ni se amplía la intervención a esos ficheros ajenos. Resolver esta reserva antes de integrar o desplegar mecanismos nuevos en producción. El 0031 desarrolla únicamente código y pruebas en laboratorio sin registro en la API; no relaja este bloqueo para despliegue.

**Hito 2 pendiente — no desplegado:** capacidades HLS firmadas por perfil, sesión autenticada y generación de drenaje; revocación y validación en master, variantes, segmentos, claves y Range; pruebas entre perfiles y sobre tokens previos al drenaje. Diseño y matriz: [DISENO-HLS-PERFIL-SESION-GENERACION-PENDIENTE.md](DISENO-HLS-PERFIL-SESION-GENERACION-PENDIENTE.md).

**Hito 3 pendiente — no desplegado:** bloquear vías alternativas de Jellyfin, escrituras de qBittorrent y lectores NTFS con evidencia de puerto, handles, reinicio y autoridad por descarga. El mutex 0030 **no** cubre esas vías. Diseño y matriz: [DISENO-AISLAMIENTO-JELLYFIN-QBIT-NTFS-PENDIENTE.md](DISENO-AISLAMIENTO-JELLYFIN-QBIT-NTFS-PENDIENTE.md).

**Hitos 4/5 permanecen bloqueados:** sin administrador enrolado ni aprobación por película; ni un solo archivo real retirado. No pausar torrents, no borrar medios ni alterar caché Jellyfin u originales compartidos. PR #2 se mantiene en borrador y sin fusionar.

## Retirada segura 0031 — capacidad HLS v2 autenticada (27/11/2026)

Informe: [AVANCE-CAPACIDADES-HLS-0031-20261127.md](AVANCE-CAPACIDADES-HLS-0031-20261127.md).

- [x] Avance real en la **rama, exclusivamente laboratorio**: `jti` único en nuevos JWT y capacidad HLS v2 HMAC ligada a cookie autenticada, perfil, película, sesión persistente, generación revocable y raíz exacta del vídeo. URLs de master/variantes/segmentos/claves se reescriben preservando contexto.
- [x] Autoridad TEMP 0031 con transacción SQLite que revisa estado, propietario, cookie, generación y reserva antes de permitir un GET. Drenaje revoca capacidades viejas y mantiene abiertas las reservas en vuelo; caída/reapertura simulada no concede autorización física.
- [x] TestClient con JWT auténtico, fuente Jellyfin ficticia y SQLite TEMP: **54/54 tests dirigidos PASS**; backend completo **1547/1547 PASS**; Ruff de los cuatro ficheros cambiados PASS; TypeScript y ESLint PASS; smoke real de solo lectura **10/10 PASS**.
- [x] Preflight real posterior, solo lectura: **4/4 películas bloqueadas**, **2/2 diarios NTFS verificados**, **permiso de borrado NO**, 0 medios borrados y 0 torrents modificados.
- [x] **Nueva brecha de aislamiento observada:** Windows ejecuta Jellyfin nativo escuchando en `0.0.0.0:8096` mientras Jellyfin Docker está publicado en `127.0.0.1:8097`; qBittorrent nativo escucha en `[::]:8080`. Los volúmenes multimedia de Jellyfin Docker son solo lectura. No se ha demostrado aún acceso LAN por cortafuegos ni el alcance del Jellyfin nativo a los mismos archivos.
- [ ] **Aún pendiente del hito 2:** integrar autoridad persistente y HLS v2 en las rutas reales (incluidos directos, `Range`, abortos y cierres de cuerpo HTTP); prohibir v1 sin una vía alternativa; probar con navegador y reproductor real. No desplegar esta versión parcial ni migrar sesiones de producción automáticamente.
- [ ] **Hito 3 necesario:** inventariar y cerrar accesos al Jellyfin nativo/Docker, Web UI qBit y lectores/handles NTFS; demostrar quietud atómica, recuperación de reinicio, exclusión de los cuatro metadatos extras y ausencia de bypass.
- [ ] **Calidad de repositorio bloqueante para despliegue:** Ruff global sigue informando **128 hallazgos preexistentes fuera del 0031**. No se ha desactivado ninguna regla ni se ha confundido Ruff parcial con Ruff completo.
- [ ] **Hitos 4/5:** identidad admin independiente, aprobación por película, diario transaccional y ejecutor Windows con rollback y bytes físicos verificados; ninguna operación destructiva hasta superar todas las barreras.

Sin despliegue de la API, cambios Docker/firewall/ACL ni paradas qBit/Jellyfin. PR #2 OPEN/DRAFT; no merge. **Primero terminar gestión de espacio y borrado seguro; después app Samsung; finalmente VIEWTV Momentos.**

## Retirada segura 0032 — rutas reales HLS v2 inyectadas solo en TestClient (27/11/2026)

Informe: [AVANCE-HLS-RUTAS-REALES-AISLAMIENTO-0032-20261127.md](AVANCE-HLS-RUTAS-REALES-AISLAMIENTO-0032-20261127.md).

- [x] Los handlers reales de `playback-info`, `stream` y `hls` admiten una dependencia **no registrada por defecto**, que permite probar el contrato HLS v2 de 0031 con una SQLite TEMP. En la aplicación actual **no hay puente HLS**: los tokens v1 existentes siguen siendo el comportamiento productivo y no autorizan borrado.
- [x] En TestClient, la barrera ASGI autenticada 0029 marca admisión solo tras reservar, y el puente 0032 exige esa marca: si se intenta inyectar v2 sin el guard, negociación, stream directo y HLS devuelven 423 **sin contacto Jellyfin**. Rechaza URLs v1, robo entre perfiles/logins, generación obsoleta y peticiones tras drenaje. Mantiene el contador hasta finalizar los cuerpos de fragmentos HTTP y libera reservas ante error.
- [x] **8/8 pruebas nuevas** de rutas reales ficticias, incluyendo un stream bloqueado concurrentemente mientras comienza drenaje y rechazo de playlist maliciosa. Backend completo **1555/1555 PASS** (dos advertencias externas), TypeScript PASS, ESLint PASS y smoke real read-only **10/10 PASS**; Ruff de los ficheros modificados PASS. La suite dirigida 0029/HLS/0032 pasa **43/43**.
- [x] **Evidencia externa read-only:** Jellyfin nativo escucha `0.0.0.0:8096`, además del Docker `127.0.0.1:8097`; qBittorrent nativo escucha `[::]:8080`. Firewall Windows `ActiveStore` incluye reglas de entrada **Allow** para Jellyfin nativo en perfiles Private/Public y para qBittorrent en Private/Public, protocolos TCP/UDP, `LocalPort=Any`, `RemoteAddress=Any`. **No se ha probado alcance real desde LAN ni las rutas de biblioteca del Jellyfin nativo**, y no se puede acreditar todavía el cierre de vías alternativas.
- [x] Preflight real solo lectura posterior: **4/4 películas bloqueadas**, **2/2 diarios NTFS verificados**, `PERMISO_DE_BORRADO_OTORGADO=NO`, cero archivos eliminados y cero torrents modificados.
- [ ] **No desplegar**: falta unificar la barrera de todos los modos en `app.main`, persistir sesiones productivas, cerrar sesiones de reproducción de clientes, asegurar reinicio/abortos, migrar sin HLS v1 y verificar navegador/TV; siguen abiertas vías alternativas de Jellyfin, qBit y lectores NTFS, y Ruff global **128 avisos**.
- [ ] Antes del borrado físico: aislamiento real de redes/handles y escrituras, autorización admin por película, journal y ejecutor Windows con rollback/medición. No detener torrents, tocar ACL/firewall/cachés ni retirar medios ahora. PR #2 OPEN/DRAFT, sin merge. Samsung después de espacio, Momentos después de Samsung.

## Retirada segura 0033 — auditoría conservadora de accesos externos (28/11/2026)

Informe: [AVANCE-BARRERA-ACCESOS-EXTERNOS-0033-20261128.md](AVANCE-BARRERA-ACCESOS-EXTERNOS-0033-20261128.md).

- [x] Implementado `scripts/viewtv_windows_accesos_externos_readonly_0033.ps1`: inventario de listeners nativos asociados a proceso, puertos y reglas de entrada Windows `Allow` por aplicación; sin rutas, credenciales, IPs de clientes ni modificaciones. Auditoría real: Jellyfin nativo y qBittorrent escuchan externamente, reglas amplias `Allow` presentes, Jellyfin Docker observado solo en loopback.
- [x] Implementado `worker/retirement_external_gate_0033.py`: contrato de informe estricto, dos observaciones, bloqueo por cambios o incoherencia; **nunca otorga permiso físico de borrado**, incluso si dejan de verse puertos.
- [x] `scripts/viewtv_retirada_accesos_gate_0033.py`: dos consultas nativas WSL/Windows reales, resultado `ESTADO_RETIRADA_0033=BLOQUEADA`, `PERMISO_DE_BORRADO_OTORGADO=NO`, cero archivos eliminados y cero torrents modificados. Sin conexión al ejecutor físico ni al servicio de producción.
- [x] **17/17 tests nuevos PASS** (parser, exposición, evidencia ausente, contradicción, manipulación). Ruff de nuevos archivos Python PASS; **backend íntegro 1572/1572 PASS** (2 advertencias externas), **TypeScript PASS**, **ESLint PASS**, smoke real read-only **10/10 PASS**.
- [x] Preflight físico read-only posterior conserva **2/2 diarios NTFS verificados**, **4/4 películas bloqueadas**, **0 borrados**, **0 cambios qBit**.
- [ ] Hito de aislamiento real pendiente: demostrar desde LAN los clientes autorizados y Jellyfin nativo, cerrar bypasses sin romper reproducción, inmovilizar un torrent exacto sin aceptar reanudación, excluir nuevas aperturas/handles por File ID NTFS, probar reinicios y carreras. Auditoría de puertos/firewall **no prueba quietud**.
- [ ] Hitos finales: identidad administrativa independiente, autorización específica por película, ejecutor Windows duradero y bytes físicos liberados; sin eliminar ninguna película ahora. PR #2 permanece abierta y draft, sin fusionar. Ruff global **128 hallazgos históricos** sin resolver.

## Retirada segura 0034 — dos handles Win32 y recuperación ficticia (28/11/2026)

Informe: [AVANCE-HARDLINKS-KERNEL-0034-20261128.md](AVANCE-HARDLINKS-KERNEL-0034-20261128.md).

- [x] Ensayos reales Windows **solo sobre archivos TEMP ficticios**: comprobación de File ID/volumen/hardlinks, denegación de apertura en origen/publicado ante `FileShare.None`, bloqueo por lector preexistente y rechazo de tercer hardlink observado.
- [x] **Dos handles Win32 `DELETE|FILE_READ_ATTRIBUTES`, `FILE_SHARE_DELETE`**, identidad verificada, `SetFileInformationByHandle(FileDispositionInfoEx, DELETE|POSIX_SEMANTICS)`: los dos unlink **de prueba** finalizan sin soltar ambos handles. Simulación de interrupción tras primer unlink, reconciliación del File ID y restauración; diario TEMP `WriteThrough`/`Flush(true)` verifica siete estados. NO demuestra recuperación de muerte abrupta/reinicio.
- [x] Suite `scripts/test_viewtv_windows_ntfs_kernel_0034.ps1`: prueba los dos scripts en procesos separados, valida código de salida y todas las etiquetas; `NTFS_0034_DOS_SUITES_SANDBOX=PASS`, **0 archivos reales borrados y 0 torrents modificados**. Regresión final backend **1572/1572 PASS**, TypeScript/ESLint PASS, smoke real read-only **10/10 PASS**, preflight **4/4 películas bloqueadas, 2/2 diarios NTFS verificados**.
- [x] **BLOQUEO EXPERIMENTAL CRÍTICO:** `CreateHardLinkW` puede añadir un tercer hardlink tanto durante `FileShare.None` como bajo ambos handles DELETE. Ni el mutex ni reservar datos son barrera completa contra cambios de nombres NTFS. **NO activar borrado real hasta impedir nuevos hardlinks mediante aislamiento efectivo de identidades y permisos**.
- [x] Auditoría Windows read-only: Jellyfin nativo y qBittorrent nativo comparten usuario con la sesión operadora de VIEWTV; una ACL que permita cambiar enlaces a esa identidad no discrimina entre ejecutor, Jellyfin y qBit. La separación requiere servicio/identidad propia y pruebas con SIDs diferentes.
- [ ] Todavía faltan: bloqueo de acceso Jellyfin directo y HLS v1, custodia qBit por descarga, guardián NTFS con permisos kernel efectivos, alta admin real, diario/ejecutor privilegiado recuperable y autorización por una película concreta. **No se ha implementado ni desplegado el ejecutor productivo.**
- [ ] PR #2 sigue OPEN/DRAFT y sin fusionar. Prioridad: terminar borrado seguro antes de Samsung y Momentos.

## Retirada segura 0035 — gate Ruff global cerrado (28/11/2026)

Informe: [AVANCE-CALIDAD-RUFF-0035-20261128.md](AVANCE-CALIDAD-RUFF-0035-20261128.md).

- [x] **Reserva de calidad abierta desde 0030 resuelta:** Ruff global `backend worker scripts` → **0 hallazgos, All checks passed!**, frente a los **128 avisos históricos**. Reglas globales sin reducir ni desactivar.
- [x] Respaldo privado previo fuera de Git: 267 fuentes Python versionadas, `/home/viewtv/viewtv-backups/0035-20261128/ruff_python_before.tar.gz`, SHA-256 `13c721efac07badd49335afacc3e8273fff47801b8bead8e94a34d1ea072cce4`. 76 ficheros históricos corregidos con Ruff y revisión AST para formato/restos.
- [x] Contratos de denegación intactos: se conservan las `ValueError` esperadas por preflights y validadores; los casos excepcionales están justificados por línea, sin cambios a las reglas globales. Validación `git diff --check` PASS.
- [x] **Backend completo 1572/1572 PASS** (2 advertencias externas), TypeScript PASS, ESLint PASS y smoke HTTP real de solo lectura **10/10 PASS**. Preflight real mantiene **4/4 películas bloqueadas**, **2/2 diarios NTFS verificados**, cero borrados y cero modificaciones de torrents.
- [ ] El éxito de calidad NO da autorización física: 0034 demostró que `CreateHardLinkW` puede añadir enlaces durante los dos handles NTFS. HLS v2 y guard de admisión aún sin despliegue, Jellyfin/qBit nativos comparten identidad operadora, la custodia de torrent no es transaccional y no hay administrador real enrolado ni película apta. **No se ejecutará borrado real sin cerrar todas las barreras y aprobación individual.**
