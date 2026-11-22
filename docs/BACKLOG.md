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
