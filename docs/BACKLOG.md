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
