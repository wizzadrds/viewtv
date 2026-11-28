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

## Retirada segura 0036 — recuento NTFS exacto frente a terceros enlaces (28/11/2026)

Informe: [AVANCE-AUDITORIA-HARDLINKS-EXACTOS-0036-20261128.md](AVANCE-AUDITORIA-HARDLINKS-EXACTOS-0036-20261128.md).

- [x] Endurecido `Test-SameHardlink` de la auditoría real **solo lectura** 0016: debe observar **exactamente 2 enlaces** en ambos nombres, mismo File ID/volumen y tamaño. Antes aceptaba 3 o más; el inventario 0018 ya exigía dos. Respaldo SHA256 privado previo fuera del repo.
- [x] Prueba negativa Windows sobre 3 hardlinks TEMP ficticios invoca esa misma función de auditoría base; la suite 0034 rechaza el tercero y mantiene las pruebas de doble handle y recuperación: **2/2 suites PASS**.
- [x] Auditoría bajo mutex 0022 en Windows real `DIARIOS_NTFS_VERIFICADOS=SI`, `AUTORIZA_ELIMINACION=NO`. Preflight integrado 0018: **2/2 diarios válidos**, **4/4 películas bloqueadas**, 0 borrados y 0 cambios de torrents.
- [ ] **Esta comprobación no impide que se creen terceros enlaces después**: falta segregación real de identidad/ACL de metadatos, custodia qBit y cierre Jellyfin/HLS, aprobación administrativa única y ejecutor recuperable. No activar borrado de producción ni fusionar PR #2 hasta demostrar todas las barreras.

## Retirada segura 0037 — aislamiento Windows por dos SIDs y auditoría real (28/11/2026)

Informe: [AVANCE-AISLAMIENTO-SIDS-ACL-0037-20261128.md](AVANCE-AISLAMIENTO-SIDS-ACL-0037-20261128.md).

- [x] Dos cuentas Windows efímeras, SIDs distintos y no administrativos, ensayadas con archivo/hardlinks TEMP ficticios. El lector puede leer pero **NO crear un hardlink adicional ni en un directorio propio con escritura**, y no puede abrir ni crear enlaces mientras el broker retiene ambos handles DELETE. El broker segregado completa ambos unlinks ficticios. Cuentas temporales eliminadas; cero servicios/ACL/medios reales modificados.
- [x] Runner PowerShell con autorización explícita de cuentas temporales, contrato exacto de 20 pruebas, informe reducido y verificación de **cero cuentas huérfanas**: SIDS_DISTINTOS_NO_ADMINISTRADORES=PASS; LECTOR_NO_CREAR_HARDLINK_DURANTE_COMMIT=PASS; BROKER_DISTINTO_SID_DOS_UNLINKS_FICTICIOS=PASS.
- [x] Auditoría solo lectura de identidad real: Jellyfin, qBit y la tarea publicadora **comparten SID operador**; **1/4** raíces con herencia ACL desactivada. Eso NO autoriza modificar toda la biblioteca ni prueba permisos efectivos de un archivo.
- [x] Parser/gate de SIDs y doble lectura de Windows, siempre fail-closed, con **29/29 pruebas específicas PASS**. Preflight real de host 0037: ESTADO_RETIRADA_0037=BLOQUEADA; 0 películas retiradas y 0 torrents modificados. **Regresión total backend 1601/1601 PASS** (2 advertencias externas), Ruff global PASS, TypeScript PASS, ESLint PASS, smoke real 10/10 PASS, NTFS Windows 0034 dos suites PASS.
- [ ] **Aislamiento productivo pendiente:** enrolar broker como identidad de servicio independiente con respaldo/rollback del host, probar una ACL temporal por película exacta con cuentas reales y qBit inmovilizado, proteger handles y metadatos de todos los enlaces, cerrar Jellyfin/HLS directo, conectar autorización admin y journal recuperable. Las cuatro películas siguen bloqueadas y el ejecutor productivo no está instalado. PR #2 sigue en borrador.

## Retirada segura 0038 — custodia durable de UN hash qBittorrent (28/11/2026)

Informe: [AVANCE-CUSTODIA-QBIT-STOP-0038-20261128.md](AVANCE-CUSTODIA-QBIT-STOP-0038-20261128.md).

- [x] Cliente qBittorrent ampliado con `stop_torrent(hash)`: admite **un hash 40/64 hexadecimal** y rechaza `all`, listas y combinaciones; nunca selecciona todos los torrents. **No usado por ninguna ruta productiva**.
- [x] Autoridad de parada de laboratorio SQLite TEMP, cerrada a transporte **`httpx.MockTransport`** y una sola descarga. Verifica medio/TMDB/diario/propiedad qBit/huella de **todos** los archivos, incluidos metadatos extra; registra `orden_pendiente` en disco con `BEGIN IMMEDIATE` y `synchronous=FULL` **antes** de enviar el POST al mock.
- [x] Recuperación sin retransmisión tras pérdida de HTTP o **muerte abrupta real de proceso hijo** después del POST al qBit ficticio; una reanudación o alteración de ficheros bloquea durablemente. Pruebas con dos llamadas concurrentes: como máximo **1 POST para el hash exacto**; nunca resuelve quietud real ni habilita borrado.
- [x] **43/43 tests nuevos PASS**; combinación qBit y custodia **134/134 PASS**, Ruff global PASS; **backend íntegro 1644/1644 PASS** (2 advertencias externas), TypeScript PASS, ESLint PASS, Ruff global PASS y smoke real solo lectura **10/10 PASS**.
- [x] Auditoría real 0026 solo GET: **2 torrents fuera de reposo seguro**, 2 archivos publicados, **4 extras protegidos (488 bytes lógicos)**. Preflight real 0018: **4/4 películas bloqueadas**, 2 diarios NTFS verificados, permiso físico NO, cero archivos eliminados, cero torrents modificados.
- [ ] **Custodia productiva sigue pendiente:** impedir reinicio/reanudación desde GUI, WebUI y otros procesos; identidad/ACL Win32 del broker real, exclusión NTFS por File ID, Jellyfin y HLS v2 efectivos, autorización administrativa por película, diario Windows recuperable y primera candidata que cumpla criterios. Ninguna orden real `stop` enviada, ningún servicio desplegado, PR #2 continúa OPEN/DRAFT sin merge.

## Retirada segura 0039 — cerca de inicios VIEWTV compartida con qBit 0038 (28/11/2026)

Informe: [AVANCE-CERCO-INICIOS-QBIT-0039-20261128.md](AVANCE-CERCO-INICIOS-QBIT-0039-20261128.md).

- [x] Adaptador ficticio `worker/retirement_qbit_start_fence_lab_0039.py` con la **misma SQLite privada 0038**: para un `start_torrent(hash)` VIEWTV, mantiene `BEGIN IMMEDIATE` durante el POST a `MockTransport` y rechaza cualquier hash con custodia registrada, pendiente, enviada, observada o bloqueada. No caduca ni se libera tras reinicio.
- [x] Integración de prueba con el **worker real** `process_one_start` sin modificar el comportamiento del servicio activo: un torrent bajo custodia queda sin iniciar y otro ajeno al cerco inicia en el fake. Prueba de orden entre alta de custodia y START en vuelo y de ocho starts simultáneos denegados.
- [x] **25/25 tests nuevos PASS**, backend completo **1669/1669 PASS** (dos advertencias externas), Ruff global PASS, TypeScript PASS, ESLint PASS, smoke read-only real **10/10 PASS**. Prueba negativa demuestra que una WebUI/cliente qBit externo **no** queda sujeto a este adaptador: puede reanudar al margen de VIEWTV y el gate 0038 lo detecta y bloquea posteriormente.
- [x] Auditoría real qBit **solo GET**: **2/2 torrents sin reposo seguro**, 4 extras protegidos (488 bytes lógicos); preflight 0018 conserva **4/4 películas bloqueadas**, 2/2 diarios NTFS verificados, 0 borrados y 0 cambios qBit.
- [ ] **No implementado como cerco real productivo:** faltan control exclusivo de todas las interfaces qBit, broker Windows/ACL y NTFS, HLS/Jellyfin externo, administración independiente y un ejecutor con journal/reinicio y medición. PR #2 sigue OPEN/DRAFT sin fusionar. No se envió `start` ni `stop` al qBit real.

## Retirada segura 0040 — auditoría real WebUI/GUI qBittorrent y gate fail-closed (28/11/2026)

Informe: [AVANCE-QBIT-WEBUI-EXTERNA-0040-20261128.md](AVANCE-QBIT-WEBUI-EXTERNA-0040-20261128.md).

- [x] Inventario Windows **solo lectura** de proceso qBit/SID, listeners, conexiones WebUI y reglas firewall por ejecutable. Del fichero INI local se extrae **solo presencia de WebUI habilitada, APIKey y contraseña PBKDF2**, jamás valores o hashes. La vinculación exacta del perfil INI al proceso queda **NO_VERIFICADA**.
- [x] Hallazgo real: qBittorrent nativo comparte SID operador, WebUI está configurada como habilitada con clave API/contraseña presentes, socket externo y firewall amplio; no se observó sesión WebUI remota durante las consultas. **No implica que un cliente externo no pueda conectarse ni que la GUI esté controlada**.
- [x] Evaluador de dos observaciones y runner Windows↔WSL, esquemas cerrados (sin rutas/SIDs/secretos, duplicados, permisos de borrado afirmativos ni fuentes incompletas). Ejecución real: `ESTADO_RETIRADA_0040=BLOQUEADA`, 0 archivos eliminados y 0 torrents modificados.
- [x] **35/35 tests del nuevo gate PASS**, backend completo **1704/1704 PASS** (2 advertencias externas), Ruff global PASS, TypeScript PASS, ESLint PASS y smoke HTTP real read-only **10/10 PASS**. Preflight NTFS real **4/4 películas bloqueadas**, **2/2 diarios verificados**, cero borrados y cero cambios de torrents.
- [ ] **Segregación productiva sigue pendiente**: migración controlada de credenciales y proceso qBit a broker SID propio, impedir START desde GUI y otros clientes, garantizar WebUI inaccesible para actores no autorizados, cerrar escrituras y terceros hardlinks por File ID, drenar Jellyfin/HLS, aprobar una película y disponer de ejecutor durable. No instalar reglas/credenciales/ACL nuevas ni interrumpir clientes sin autorización expresa. PR #2 continúa OPEN/DRAFT.

## Retirada segura 0041 — interlock unificado de 7 fuentes, 8 informes (28/11/2026)

Informe: [AVANCE-INTERLOCK-UNIFICADO-0041-20261128.md](AVANCE-INTERLOCK-UNIFICADO-0041-20261128.md).

- [x] `worker/retirement_unified_gate_0041.py`: parser conservador de los informes 0018/0019/0026/0027/0033/0037/0040; rechaza permisos positivos, ausencia de fuentes, valores malformados, campos ajenos, alteraciones qBit y contradicciones de totales de películas/diarios/archivos extras. **No dispone de capacidad de unlink ni start/stop**.
- [x] `scripts/viewtv_retirada_interlock_0041.py`: ejecuta solo scripts estáticos de auditoría de solo lectura, sin argumentos del usuario, repite preflight 0018 antes y después de seis inspecciones y exige coherencia temporal de los 8 informes. **Exit 2** si fuentes inválidas; **exit 3** cuando 8 informes coherentes pero retirada BLOQUEADA. **Nunca exit 0**: cero archivos eliminados y cero torrents modificados.
- [x] **49/49 tests nuevos PASS**, Ruff global PASS. Ejecución sobre Windows/WSL reales: **8/8 informes verificados**, 6 barreras productivas pendientes y `ESTADO_RETIRADA_0041=BLOQUEADA`. **backend completo 1753/1753 PASS** (2 advertencias externas), Ruff global PASS, TypeScript PASS, ESLint PASS, smoke HTTP real solo lectura 10/10 PASS.
- [ ] Esta herramienta NO instala aislamiento: Jellyfin directo/HLS v1, broker SID/ACL NTFS, GUI/WebUI qBit externa, recuperación del ejecutor y admin por película siguen pendientes. Las cuatro películas del último preflight siguen bloqueadas; PR #2 OPEN/DRAFT, sin fusionar.

## Retirada segura 0042 — muerte real de proceso a mitad de unlink NTFS (28/11/2026)

Informe: [AVANCE-RECUPERACION-CRASH-NTFS-0042-20261128.md](AVANCE-RECUPERACION-CRASH-NTFS-0042-20261128.md).

- [x] Ensayo Windows con **TerminateProcess real de dos procesos hijo distintos**: primera muerte tras `File.Delete` del hardlink publicado TEMP, segunda tras `SetFileInformationByHandle(FileDispositionInfoEx)` del primer hardlink, manteniendo dos handles DELETE adquiridos antes del corte.
- [x] Diario de intención `FileOptions.WriteThrough` y `Flush(true)` **antes** de cada operación, huella de File ID NTFS (volumen+índice alto/bajo), tamaño, SHA256 y fases de recuperación. Procesos distintos reconstruyen el **mismo File ID**; repetir `Recover` y `RecoverNative` es idempotente. Tercer hardlink y lector preabierto **denegados** antes de alterar el par final.
- [x] Fin del sandbox: dos unlinks Win32 bajo dos handles nativos, repetición de `Finish` sin doble borrado, limpieza del directorio GUID. **Runner 0042 ejecutado dos veces en Windows, 2/2 PASS**, sin rutas ni parámetros de producción; cero borrados de películas reales y cero cambios de torrents.
- [x] NTFS 0034 **2/2 suites PASS**; preflight NTFS real 0018 **4/4 películas bloqueadas** y **2/2 diarios verificados**; custodia qBit 0026 **2/2 torrents sin reposo**, **4 extras protegidos / 488 bytes lógicos**, 0 eliminaciones y 0 cambios qBit. **Backend completo 1753/1753 PASS**, 2 advertencias externas; Ruff global, TypeScript, ESLint, smoke HTTP real **10/10 PASS**.
- [ ] Esta prueba NO equivale a caída eléctrica, recuperación de servicio real ni commit después del segundo unlink sin journal; sigue sin instalarse broker productivo, cuentas/ACL segregadas, custodia qBit y cierre WebUI/GUI/Jellyfin/HLS, autorización admin por película y medida de espacio físico. **No habilitar borrado real ni fusionar PR #2.**

## Retirada segura 0043 — conciliar crash después del segundo unlink NTFS (28/11/2026)

Informe: [AVANCE-RECUPERACION-POSTCOMMIT-0043-20261128.md](AVANCE-RECUPERACION-POSTCOMMIT-0043-20261128.md).

- [x] Se amplió **solo el sandbox 0042**, sin parámetros de medios: `TestAfterBoth` y dos procesos hijos `KillBoth`/`ReconcileBoth`. Journal `COMMIT_PREPARADO` con `WriteThrough`+`Flush(true)`, dos handles DELETE del mismo File ID y muerte real de Windows **después de ambos unlinks nativos y antes del journal FINALIZADO**.
- [x] Proceso distinto reconcilia las fases y dos nombres ausentes sin ejecutar ningún otro unlink; `ReconcileBoth` repetido confirma idempotencia. Si otro archivo **ficticio** ocupa uno de los nombres, aborta la conciliación y conserva el archivo sin modificar. El ensayo limpia su propia intrusión controlada únicamente tras verificar su marca.
- [x] `test_viewtv_windows_postcommit_recovery_0043.ps1`: **2/2 ejecuciones independientes PASS** con salida estricta de trece líneas y dos sandbox GUID limpiados. Runner anterior 0042 **2/2 PASS** tras extender su script. Cero películas reales borradas y cero torrents modificados.
- [x] Preflight real posterior 0018: **4/4 películas bloqueadas, 2/2 diarios NTFS válidos**; qBit 0026: **2/2 torrents sin reposo seguro**, cuatro extras protegidos (488 bytes lógicos). **Backend completo 1753/1753 PASS** (2 advertencias externas); Ruff global, TypeScript, ESLint, smoke HTTP real **10/10 PASS**; NTFS kernel 0034 dos suites PASS; Windows TEMP sin directorios residuales del ensayo.
- [ ] **Producción NO habilitada**: no se han validado apagón eléctrico, ausencia de enlaces fuera de TEMP, volumen realmente liberado, autoridad de broker SID/ACL, custodia qBit que excluya GUI/WebUI, Jellyfin/HLS ni admin por película. PR #2 sigue sin merge ni despliegue.

## Retirada segura 0044 — aprobación administrativa única por película/descarga y File ID (28/11/2026)

Informe: [AVANCE-RESERVA-UNICA-PELICULA-NTFS-0044-20261128.md](AVANCE-RESERVA-UNICA-PELICULA-NTFS-0044-20261128.md).

- [x] **Corrección real del consumidor administrativo 0019** (no usado por el servicio activo): además de PRIMARY KEY(nonce), exige índices únicos SQL transaccionales por **medio** y **descarga**, y comprueba con PRAGMA que son completos, realmente UNIQUE y apuntan a la columna correcta. Segunda firma con otro nonce no rearma una película; un diario anterior con duplicados falla cerrado. Copia privada del fichero previo fuera de Git, SHA256 `aee2a1dc9268c3a999d640e454a265d1665ca77c61c1337ad0a641364c34864e`.
- [x] Laboratorio de reserva 0044: enlaza criptográficamente huella del preflight completo, película, descarga, hash qBit, volumen + File ID NTFS, exactamente dos enlaces, tamaño y SHA256. Comparación doble de evidencias, firma HMAC 0019 vigente, qBit ficticio parado y dos GET con `MockTransport` antes de un único `BEGIN IMMEDIATE` del SQLite privado compartido con el cercado START 0039; `UNIQUE` por medio/descarga/hash/nonce/File ID. **No devuelve ni contiene capacidad de unlink**.
- [x] **53/53 tests de reserva PASS** (incluida muerte real de proceso hijo justo después de consumo, reinicio, concurrencia de 16 reservas, reanudación por WebUI ficticia, tercer hardlink y File ID alterado) + **7 tests nuevos del consumidor 0019**, combinados con las pruebas anteriores de autorización **99/99 PASS**; **backend completo 1813/1813 PASS** (2 advertencias externas), Ruff global PASS, TypeScript PASS, ESLint PASS, smoke HTTP solo lectura **10/10 PASS**. Interlock 0041 real **8/8 informes coherentes** pero retirada BLOQUEADA por seis barreras productivas.
- [x] Preflight administrativo real: **4 películas, 0 candidatas aptas**, 0 aprobaciones emitidas; preflight 0018 **4/4 bloqueadas**, NTFS **2/2 diarios verificados**, qBit 0026 **2/2 torrents sin reposo seguro** y **4 extras preservados (488 bytes lógicos)**. Cero películas borradas, cero torrents modificados.
- [ ] **El borrado real continúa bloqueado**: el File ID de 0044 proviene de testigo sintético, no de broker Windows kernel; no hay SID independiente ni control efectivo de GUI/WebUI, no se ha desplegado HLS v2/drain Jellyfin, ni existe aprobación firmada real para una película apta, commit NTFS productivo o medición de bloques liberados. Mantener PR #2 OPEN/DRAFT, sin fusionar ni desplegar.

## Retirada segura 0045 — firma y reserva con un COMMIT SQLite compartido (28/11/2026)

Informe: [AVANCE-AUTORIDAD-ATOMICA-RETIRADA-0045-20261128.md](AVANCE-AUTORIDAD-ATOMICA-RETIRADA-0045-20261128.md).

- [x] Consumidor administrativo `consumir_en_transaccion_0045` extraído del 0019: firma HMAC y prueba exacta verificadas, schema SQL e índices únicos comprobados y consumo dentro de una **transacción ya abierta** sin hacer COMMIT propio ni autorizar unlink. `consumir_ticket_una_vez` reutiliza ahora este mismo núcleo; se mantiene la interfaz anterior y su ledger independiente de ensayo.
- [x] Reserva 0044 actualizada para consumir la firma HMAC y almacenar la película/File ID bajo el **mismo BEGIN IMMEDIATE y COMMIT** del diario qBit simulado 0038/0039. Si falla cualquiera de los INSERTs, no queda ni consumo ni reserva. Un `estado` reabierto exige relación exacta `consumos` + `reservas` + `custodia`; reserva vieja o malformada sin una aprobación consumida coincidente se bloquea. Verifica índices realmente únicos de toda la tabla, no solo nombre de tabla.
- [x] **19/19 nuevas pruebas 0045 PASS**: dos muertes reales de proceso de laboratorio con `os._exit(84/85)` antes del COMMIT, rollback completo incluso si ya se insertaron ambas filas, reintento seguro con la misma firma, trigger de fallo SQL, divergencia de seis campos y cinco tablas con índices engañosos. No hay operaciones de producción. **Backend completo 1832/1832 PASS** (2 advertencias externas), Ruff global PASS, TypeScript/ESLint PASS y smoke real HTTP solo lectura **10/10 PASS**. Interlock 0041 **8/8 informes** válidos pero sigue BLOQUEADA por seis barreras.
- [x] Preflight 0018 real 4/4 películas bloqueadas, diarios NTFS 2/2 verificados; preflight administrativo 0019 0/4 películas candidatas y 0 aprobaciones; qBit 0026 dos torrents sin reposo y cuatro extras protegidos, 488 bytes lógicos. El interlock 0041 se mantiene denegatorio aunque sus ocho fuentes concuerden.
- [ ] **El laboratorio NO es un ejecutor productivo**. Las otras GUI/WebUI de qBit, HLS v1/Jellyfin directo, SID/ACL compartidos, terceros hardlinks, reinicio/eléctrica, aprobación por película elegible y medición física siguen sin cierre. Tampoco están unificados de forma global los clientes que usen otro archivo ledger. PR #2 continúa OPEN/DRAFT y NO se despliega ningún cambio sin autorización de mantenimiento.

## Retirada segura 0046 — START qBit con intención durable ANTES del POST (28/11/2026)

Informe: [AVANCE-INTENCION-START-QBIT-0046-20261128.md](AVANCE-INTENCION-START-QBIT-0046-20261128.md).

- [x] Arreglada en laboratorio la carrera del 0039: el START antes se enviaba dentro de una única transacción que desaparecía al morir el proceso. Ahora **se confirma una intención persistente antes del POST mock**; `pendiente` tras fallo/crash y `confirmada` tras respuesta válida **bloquean nuevas custodias del mismo hash y reintentos de START** hasta reconciliación expresa. No hay TTL ni borrado automático.
- [x] Dos muertes reales de procesos hijos (después del COMMIT y antes de POST, y durante el POST simulado) + reapertura del SQLite demuestran que la intención sobrevive sin reenvío. La base existente con tabla START borrada o falsa no se repara en silencio. Los hashes ajenos siguen funcionando en el simulador.
- [x] **20/20 tests nuevos y 88/88 dirigidos 0038+0039+0046 PASS**. El test anterior 0039 start-primero ahora exige negar el registro de custodia posterior. **Regresión backend total 1852/1852 PASS** (2 advertencias externas); Ruff global PASS, TypeScript PASS, ESLint PASS y smoke HTTP real solo lectura **10/10 PASS**. Auditoría 0041 real: 8/8 informes verificables pero seis barreras y retiro BLOQUEADA.
- [x] Preflight real 0018: **4/4 películas bloqueadas, 2/2 diarios NTFS válidos**; admin 0019: **0 candidatas**; qBit 0026: **2 torrents sin reposo y 4 extras protegidos, 488 bytes lógicos**. Interlock 0041 **8/8 informes coherentes, BLOQUEADA** por seis barreras productivas. Cero cambios qBit, cero películas eliminadas.
- [ ] qBit directo GUI/WebUI, lectores Jellyfin/HLS v1, broker SID/ACL kernel, autorización concreta de una película elegible y prueba de espacio liberado todavía NO están aislados ni desplegados. PR #2 sigue OPEN/DRAFT, sin merge.

## Retirada segura 0047 — ACL Win32 de pipe y token restringido (28/11/2026)

Informe: [AVANCE-PIPE-BROKER-SID-0047-20261128.md](AVANCE-PIPE-BROKER-SID-0047-20261128.md).

- [x] Ensayo Windows real **sin crear cuentas**: `NamedPipeServerStream` temporal con DACL de una sola ACE para el SID operador; token con ese SID deshabilitado por `CreateRestrictedToken` **no puede conectar**, token autorizado sí. Comando `START all` rechazado por la política de hash sintético; ninguna petición qBit real. Pipe/handles cerrados al terminar.
- [x] Auditor de dos ejecuciones Windows y gate fail-closed 0047: informe de diez líneas cerrado, no admite SIDs/credenciales/valores de permisos engañosos, salida **3 si se verifican ambas pero sin permiso** y 2 si fallan, nunca 0. **2/2 ensayos Windows PASS**, **47/47 nuevas pruebas Python PASS**. **Backend completo 1.899/1.899 PASS** (2 advertencias externas), Ruff global PASS, TypeScript/ESLint PASS, smoke HTTP real **10/10 PASS**. Preflight 0018 real **4/4 películas bloqueadas y 2/2 diarios NTFS verificados**; custodia qBit real **2 torrents no seguros, 4 extras protegidos**; interlock 0041 **8/8 informes pero seis barreras pendientes**, cero borrados y cero cambios de torrents.
- [ ] **Esto NO instala el broker Windows**: el pipe está asociado al SID del operador del ensayo, no a una identidad no interactiva distinta. La GUI qBit del mismo SID podría seguir conectándose; se deben separar credenciales, qBit WebUI/GUI, ACL del File ID, Jellyfin/HLS y aprobar una película elegible. El borrado productivo queda bloqueado, PR #2 OPEN/DRAFT.

## Retirada segura 0048 — verificar token real del peer Win32, no SID en payload (28/11/2026)

Informe: [AVANCE-PEER-WIN32-PROTOCOLO-0048-20261128.md](AVANCE-PEER-WIN32-PROTOCOLO-0048-20261128.md).

- [x] Tubería ficticia con una ACE SID de operador y `RunAsClient` / `WindowsIdentity.GetCurrent(true)` del lado **servidor**; no se acepta un supuesto SID proporcionado dentro del comando. Gramática `VT48|MOCK_START|hash exacto|nonce` deniega `START all`, hash ajeno, payload adicional y repetición del mismo nonce; solo respuestas de prueba, no se envía nada a qBit.
- [x] Windows directo **PASS**; runner WSL con **2/2 informes válidos** y salida BLOQUEADA, código 3 o 2, jamás 0. **50/50 pruebas nuevas PASS**, **backend completo 1.949/1.949 PASS** (2 advertencias externas), Ruff global PASS, TypeScript PASS, ESLint PASS y smoke HTTP real solo lectura **10/10 PASS**. Preflight real 0018 **4/4 películas bloqueadas y 2/2 diarios NTFS válidos**; qBit 0026 **2/2 torrents no seguros, 4 extras protegidos**; interlock 0041 **8/8 informes, seis barreras pendientes**. No se instalan cuentas, ACL de producción, sockets TCP, servicios ni herramientas de borrado.
- [ ] La prueba continúa con el **SID del operador**, no con broker productivo distinto. Nonces solo en memoria (no durables), falta timeout de frames frente a cliente malicioso con el mismo SID. No constituye aislamiento de GUI/WebUI qBit, Jellyfin/HLS ni excluye terceros hardlinks NTFS; no hay película elegible y todo borrado permanece denegado. PR #2 abierta/borrador, sin merge.

## Retirada segura 0049 — diario de nonce antes de comando mock (28/11/2026)

Informe: [AVANCE-NONCE-IPC-DURABLE-0049-20261128.md](AVANCE-NONCE-IPC-DURABLE-0049-20261128.md).

- [x] En **Windows TEMP GUID** se persiste una intención `CREATE_NEW` + `WriteThrough` + `Flush(true)` **antes de una hipotética orden IPC**. Hijo Windows muerto con `TerminateProcess` después de escribir: nuevo proceso niega la repetición del mismo nonce y el mismo nonce con otro hash. No hay POST real.
- [x] Carrera de **cuatro procesos**, un único ganador; lectores de registro todavía en escritura se **deniegan sin reintento inseguro**. Tras completar, se compara el registro exacto. Corrupción del diario denegada. Las dos ejecuciones de Windows **2/2 válidas**, **54/54 pruebas Python PASS**, **backend completo 2.003/2.003 PASS** (2 advertencias externas), Ruff global PASS, TypeScript/ESLint PASS, smoke HTTP solo lectura **10/10 PASS**. Preflight real **4/4 películas bloqueadas, 2/2 diarios NTFS verificados**, qBit **2 torrents no seguros, 4 extras protegidos**, interlock real **8/8 informes pero seis barreras pendientes**. El limpiador exclusivo del ensayo TEMP eliminó **2 carpetas residuales propias** de pruebas fallidas, 0 archivos de medios reales, 0 torrents.
- [ ] Este ledger aún **no está integrado con el pipe 0048**, no usa cuenta broker con SID distinto y no aporta aislamiento de GUI/WebUI, Jellyfin/HLS ni NTFS productivo. No garantiza tolerancia a pérdida de alimentación ni espacio recuperado. PR #2 sigue OPEN/DRAFT, retirada real BLOQUEADA.

## Retirada segura 0050 — peer Windows y nonce durable en la MISMA petición (28/11/2026)

Informe: [AVANCE-PIPE-PEER-NONCE-INTEGRADO-0050-20261128.md](AVANCE-PIPE-PEER-NONCE-INTEGRADO-0050-20261128.md).

- [x] Ahora el **mismo** servidor de tubería Win32 valida el SID real de cliente con `RunAsClient`, verifica hash/gramática mock y confirma `FileMode.CreateNew` + `WriteThrough` + `Flush(true)` de su nonce **antes de responder**. `TerminateProcess` mata de verdad al hijo inmediatamente después; un nuevo proceso abre otra tubería y **rechaza replay**, SID inyectado y hash ajeno.
- [x] Cuatro pares de pipe cliente-servidor compiten por un nonce: un solo registro aceptado, resto denegado y contenido final verificado. Diario falsificado bloquea. Se limpió el sandbox GUID ficticio. **2/2 ensayos Windows integrados válidos, 56/56 tests Python PASS, backend completo 2.059/2.059 PASS** (2 advertencias externas), Ruff global PASS, TypeScript y ESLint PASS, smoke HTTP real solo lectura **10/10 PASS**. Preflight real **4/4 películas bloqueadas**, admin **0 candidatas**, qBit **2 torrents no seguros y 4 extras protegidos**, interlock 0041 **8/8 fuentes, seis barreras pendientes**. Código del runner: 3 si auditado pero bloqueado, 2 si incompleto, nunca 0.
- [ ] **No es broker productivo**: sigue utilizando el SID operador, no conecta a qBit host ni impide su GUI/WebUI; la intención es TEMP y no garantiza persistencia ante apagón, y la lectura de frames no está endurecida contra cliente malicioso. No hay permiso de unlink ni película elegible. Mantener PR #2 OPEN/DRAFT sin fusionar.

## Retirada segura 0051 — inventario de producción y plan de despliegue reversible (28/11/2026)

Informe y plan: [PLAN-MIGRACION-BROKER-WINDOWS-0051-20261128.md](PLAN-MIGRACION-BROKER-WINDOWS-0051-20261128.md).

- [x] Nueva vía de **solo lectura** `worker/retirement_migration_plan_0051.py` + `scripts/viewtv_aislamiento_dryrun_0051.py` que reúne **dos lecturas Windows** de cada auditor 0033 (puertos/firewall/Jellyfin), 0037 (SIDs y ACL) y 0040 (qBit GUI/WebUI). Tres fuentes completas, seis observaciones consistentes, salida `BLOQUEADA` y código no cero: 3 si se puede planificar pero no desplegar, 2 si falta evidencia. No filtra identidades, IPs, secretos, rutas multimedia ni hashes.
- [x] Prueba contra informes falsificados/duplicados/inestables y **SID de qBit contradictorio entre 0037/0040**; ningún estado de laboratorio ni credencial presente autoriza instalar el broker o retirar una película. **71/71 nuevas pruebas Python PASS**, **backend completo 2.130/2.130 PASS** (2 advertencias externas), Ruff global PASS, TypeScript PASS, ESLint PASS y smoke HTTP real de solo lectura **10/10 PASS**. Auditoría 0051 real: 3/3 fuentes con 6 observaciones coherentes; preflight 0018: 4/4 películas bloqueadas, 2/2 diarios NTFS válidos; qBit 0026: dos torrents no seguros y cuatro extras protegidos; interlock 0041: 8/8 informes, seis barreras pendientes. Solo lectura, sin operaciones productivas.
- [x] **Diagnóstico real:** qBit, Jellyfin y publicador comparten SID del operador, ACL de raíces aún heredadas (menos de 4/4 protegidas), WebUI nativa qBit activa con listener/firewall amplio y Jellyfin nativo accesible externamente. No se han revelado secretos, ni detenido torrents, ni modificado reglas, ACL, cuentas o servicios.
- [x] **Runbook técnico de seis fases** con condiciones previas, aceptación y reversión: (01) inventario y backout, (02) broker no interactivo y secretos segregados, (03) qBit GUI/WebUI y START exclusivo por hash, (04) File ID NTFS y prueba negativa de tercer hardlink, (05) Jellyfin HLS v2 y drenaje, (06) apagón de laboratorio, autorización individual, crash y prueba de espacio físico. Cada etapa requiere decisión expresa de mantenimiento antes de tocar producción.
- [ ] **Sin autorización actual de mantenimiento ni de película elegible**; las 4 películas reales están bloqueadas, 2 torrents siguen sin reposo, los 4 extras qBit quedan protegidos. PR #2 continúa OPEN/DRAFT, sin fusión/despliegue ni permiso de unlink.
