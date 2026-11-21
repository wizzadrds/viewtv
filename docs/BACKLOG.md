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
