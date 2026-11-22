# Idea futura — VIEWTV Momentos: descubrimiento de películas con clips verticales para televisión

**Fecha de registro:** 22/11/2026.
**Estado:** idea de producto / propuesta de diseño. **NO implementada, NO desplegada.**
**Proyecto y rama:** `wizzadrds/viewtv`, `viewtv-seguimiento-descargas-0012`, PR #2 abierto/en borrador.
**Prioridad:** **después** de terminar y validar la app Samsung instalable con diseño profesional y carátulas a color. No desplaza la validación de cohesión carátula ↔ fuentes.
**Inspiración de interacción:** feed vertical tipo TikTok, pero diseñado desde el principio para pantalla 16:9, mando Samsung y descubrimiento de películas.

## 1. Visión del propietario

Un apartado llamado provisionalmente **«Momentos»** que enseñe clips **verticales 9:16** de escenas o momentos especialmente llamativos de películas: humor, acción, emoción, fotografía, etc. El usuario pasa al siguiente clip mediante el mando, sin tener que escribir una búsqueda. Si le interesa lo visto, pulsa **OK / «Ver película»** y VIEWTV le lleva **a la ficha de la misma película**, desde la que puede reproducirla si está disponible en su biblioteca autorizada.

La finalidad es que resulte **atractivo, cómodo y entretenido**, no maximizar el tiempo de pantalla mediante reproducción compulsiva. Debe ser fácil salir, buscar una película concreta y gestionar las recomendaciones.

**Principio fundamental: cada clip debe estar enlazado de forma comprobable a la película exacta.** No puede mandar a un remake, secuela u otra película porque compartan palabras.

## 2. Experiencia de diez pies: televisor y mando

- Entrada «Momentos» en la pantalla principal de la futura app Samsung. Puede aparecer también como carrusel discreto de «Descubre un momento», sin sustituir Explorar ni Biblioteca.
- Pantalla 16:9: **clip 9:16 centrado**, con laterales de color basados en la carátula o fondo suavemente desenfocado; nunca estirar horizontalmente el vídeo. Se reserva un lateral para título, año, géneros, progreso, accesibilidad y llamada a la acción; evitar texto encima de caras o subtítulos.
- Las carátulas conservan **sus colores originales**, contraste legible y tipografía visible desde el sofá. Transiciones suaves, sin parpadeos ni movimientos de cámara añadidos.
- Navegación **↓ siguiente**, **↑ anterior**, **OK abrir ficha / ver**, **Volver salir al origen**, **Play/Pausa** pausa el clip, **← mostrar información** (o foco equivalente), opción visible para silenciar, activar subtítulos y «No me interesa».
- El foco del mando **siempre es visible**. Sin gestos táctiles obligatorios, scroll horizontal oculto ni botones que solo respondan al ratón.
- Clips de unos **8–25 segundos** como punto de partida (duración ajustable), con pausa inmediata. Evitar arranque de audio por sorpresa: iniciar en silencio o respetar consentimiento/preferencia explícita. No precargar decenas de vídeos.
- Si el usuario pulsa OK sobre un clip: abrir **la película identificada por `tmdb_id` y, si existe, `jellyfin_item_id`**, mostrando su carátula en color, año y sinopsis. Si hay película local reproducible, ofrecer «Reproducir desde el inicio» y «Continuar». **Opcional posterior:** «Ver escena en la película» con un salto temporal verificado. Si no está disponible, ficha informativa y acción manual de solicitud existente, **nunca descarga automática**.
- Al volver, conservar la posición del feed y el clip seleccionado. Si la app pierde conexión, mostrar reintento y carátula estática, sin bucle infinito de «cargando».
- Respetar perfiles, edad, configuración de spoilers, subtítulos, idioma, reducción de movimiento y controles parentales. La cruceta, Back y los estados sin red se prueban en **Samsung real**, no solo en navegador de ordenador.

### Ejemplo concreto (solo ilustrativo; no fuente real)

1. «Momentos» muestra un fragmento vertical de una película **de la biblioteca y con derechos de uso del clip**.
2. El espectador pulsa ↓ y aparecen otros momentos; ve el título/año y una insignia de disponibilidad.
3. Le interesa uno: OK abre la ficha **de ese mismo ID de película**.
4. Si la película está en Jellyfin, el botón «Ver ahora» inicia su reproducción; si no, no se inventa disponibilidad ni se empieza ninguna descarga.
5. Volver regresa exactamente al clip en el que estaba.

## 3. Fuentes de vídeo y derechos: imprescindible antes de construir

**No se presupone el derecho a recortar, distribuir o retransmitir escenas de cualquier película.**
Opciones que deben validarse, por este orden:

1. **Clips promocionales con licencia y condiciones claras de reproducción** para la app/entorno previstos, respetando expiración, geografía, atribución y límites de redistribución. Un tráiler encontrado en Internet **no** concede automáticamente licencia para recortarlo ni re-subirlo.
2. Para medios **autorizados** de la biblioteca personal, valorar una vista previa **local y privada** únicamente si el usuario tiene derechos para crear y mostrar esos extractos conforme a los permisos aplicables. No compartir clips fuera de la red privada ni publicar material de terceros.
3. Fallback seguro si no existen clips utilizables: **carátula a color + microdescripción + botón «Abrir película»**. La sección debe seguir siendo útil sin inventar vídeos ni incumplir permisos.

No reutilizar enlaces torrent como clips, no raspar redes sociales, no usar vídeos sin licencia y no descargar películas o clips automáticamente para generar contenido. Establecer procedencia y estado de autorización de cada clip antes de mostrarlo.

## 4. Arquitectura candidata (solo diseño, sin migraciones ahora)

Propuesta de entidad `Momento` **futura**:
- `id` y `tmdb_id` validados; `jellyfin_item_id` opcional y comprobado al reproducir.
- `titulo`, `anio`, `poster`/fondo referenciados a la ficha (metadatos no identifican por sí solos el vídeo).
- `clip_uri` local o de proveedor autorizado en lista de dominios permitidos; **nunca URL arbitraria del navegador**. Identificador de licencia/procedencia, propietario, vigencia y restricciones de visualización.
- `inicio_ms`, `fin_ms` si un extracto se corresponde con un medio local autorizado; no usar offsets si son un tráiler autónomo o un archivo distinto. `aspect_ratio`, códec y pistas/subtítulos.
- `spoiler_level`, calificación por edad, idioma y revisión editorial. Estado `pendiente/validado/retirado`.
- Identificadores externos de la ficha **no** equivalen a hashes torrent; la asociación final con medio local debe verificar identidad y disponibilidad.

**Flujo de datos previsto:** catálogo de momentos validados → API paginada y con cache de corta duración → cliente de televisión con un clip en reproducción y precarga limitada del siguiente → acción OK que resuelve la película vía API autenticada → ficha de película y reproducción solo desde Jellyfin autorizado. Los enlaces de archivo no se exponen a otros perfiles ni se convierten en accesos directos sin control.

Diseño inicial: selección **editorial/manual** de una pequeña colección autorizada. Reconocimiento automático de «mejores escenas» mediante IA o heurísticas se consideraría **otra fase**, después de resolver derechos, spoilers, costes, calidad, sesgos y consentimiento. No generar clips de material protegido por defecto.

## 5. Curación, seguridad y recomendación responsable

- No mostrar spoilers fuertes por defecto: filtros «sin spoilers», «avanzados» y aviso previo; no revelar desenlaces con miniaturas, subtítulos o títulos.
- No mostrar contenido para adultos o violencia explícita a perfiles infantiles. Revisar cada clip; permitir ocultar, denunciar material inapropiado y retirar clips.
- Priorizar diversidad de géneros, novedades de la biblioteca y elección explícita («Más como esta», «No me interesa»), sin inferir información sensible.
- **No** autoplay de la película completa, ni reproducción interminable obligatoria, ni patrones que dificulten salir. El usuario controla pausa y audio.
- Métricas agregadas y optativas si llegan a necesitarse: clips abiertos, fichas consultadas y fallos de navegación/reproducción. Sin vender historial ni registrar innecesariamente escenas o preferencias personales.

## 6. Plan de ejecución futuro por hitos

**Dependencia 0 — App Samsung profesional:** primero app instalada con icono, carátulas a color, interfaz para mando, autenticación de perfiles y reproducción probada en TV real. Conservar `/tv.html` como fallback hasta que la nueva app esté validada.

**Hito A — Prototipo de UX sin vídeo real:** maquetas en la futura app Tizen con contenido ficticio, navegación arriba/abajo, foco claro, OK→ficha y Volver→posición; accesibilidad y tamaños de TV. No tocar torrents.

**Hito B — Piloto cerrado:** entre 5 y 15 clips propios/promocionales autorizados y metadatos auditados. Probar duración, encuadre vertical, códecs Tizen y subtítulos. Permitir el fallback estático si un clip falla.

**Hito C — Integración de catálogo:** lista paginada de `Momento`, correspondencia exacta de `tmdb_id` y disponibilidad Jellyfin; perfiles, restricciones de spoilers y acciones «No me interesa». Todas las reproducciones siguen pasando por las autorizaciones actuales.

**Hito D — Pulido:** velocidad de carga, 1 clip activo, siguiente precargado con presupuesto de datos y memoria, reanudación de navegación, medición optativa de fallos, pruebas de mando y reconexión. Un recomendador avanzado es opcional y no condiciona el MVP.

## 7. Criterios de aceptación antes de afirmar «funciona»

- En Samsung real: ↑/↓/OK/Volver/Play/Pausa funcionan con foco visible, con y sin mando Bluetooth, si procede.
- Clip 9:16 **sin deformar** en 16:9, carátula y textos **a color y legibles**, sin reproducción de audio inesperada.
- **100 %** de clips piloto enlazados a **ID TMDB correcto**; OK no abre secuelas ni remakes distintos.
- Sin media Jellyfin disponible: ficha visible y **ninguna reproducción/descarga iniciada**. Con biblioteca local: abrir ficha y permitir playback autorizado, comprobado físicamente en TV.
- Clip caducado, sin licencia, no permitido por edad o marcado como spoiler: no se reproduce.
- Sin conexión, vídeo incompatible o timeout: alternativa estática y reintento manual, sin pantalla congelada.
- Pruebas aisladas y documentación: código, tests, informe, respaldo verificado, commit en español, push solo a `viewtv-seguimiento-descargas-0012`; PR #2 continúa **OPEN/DRAFT**.

## 8. Decisiones que quedan por tomar

- Modelo/año del Samsung y versión Tizen admitida; forma viable de instalar la app.
- Disponibilidad real de clips/promociones **con licencia** para la experiencia propuesta.
- Si la acción OK abre directamente la ficha, inicia la película local o ofrece ambas opciones. **Propuesta inicial:** ficha primero para evitar reproducciones accidentales.
- Clip centrado o desplazado con panel lateral; probarlo desde el sofá antes de codificar.
- Qué clases de spoiler y calificación se permitirán por perfil.
- Si la personalización es manual o hay consentimiento explícito para señales mínimas de uso.

**Estado de entrega de esta idea:** únicamente documentación y registro de backlog.
**No se ha generado un clip, cambiado base de datos, desplegado servicios ni iniciado descarga alguna.**
