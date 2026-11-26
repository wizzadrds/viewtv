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
