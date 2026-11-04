# VIEWTV — Especificación funcional, progreso y tareas pendientes

Este documento amplía docs/plan-operativo.md. Resume el planteamiento funcional inicial y distingue lo que ya está hecho de lo que falta. Consultarlo antes de continuar el desarrollo.

## 1. Visión del producto

VIEWTV será una PWA doméstica con estética de plataforma de streaming, en español de España, pensada para Android TV y Fire TV y manejable con mando a distancia.

Principio central:
- El catálogo, metadatos, carátulas, perfiles y estados son persistentes y ocupan poco espacio.
- Los archivos de vídeo son temporales y viven en una caché con cuota configurable, inicialmente 80 GB.
- La caché del navegador puede conservar el catálogo para mostrar la última información conocida cuando el servidor no esté disponible.
- El equipo se enciende manualmente cuando se va a utilizar; al arrancar los servicios, la PWA debe reconectarse automáticamente.
- Dos perfiles protegidos por PIN: Adultos e Infantil. No exponer servicios a Internet en la primera versión.

## 2. Experiencia funcional prevista

### Catálogo y navegación
- Inicio con filas horizontales: Continuar viendo, Novedades, Tendencias, Por género y Fijados.
- Pósteres verticales 2:3.
- Ficha con backdrop, sinopsis, año, duración, géneros, reparto, calidad, audio, disponibilidad y títulos similares.
- Búsqueda con teclado en pantalla y navegación completa con cruceta, Enter y Atrás.
- Estados vacíos, error, carga y servidor apagado; skeletons en vez de spinners.
- Administración de escritorio con cola, almacenamiento, ajustes y registros.

### Acciones de una ficha
- Ver ahora: crea una solicitud para contenido que el usuario tenga derecho a obtener; si el archivo ya está en caché, permite reproducirlo.
- Mantener: fija un elemento para que la política de expulsión no lo elimine automáticamente.
- Borrar: elimina el archivo temporal respetando la protección de elementos en reproducción o con transferencia activa.
- Mostrar si está disponible al instante o si requiere una operación pendiente. No afirmar que existe una fuente hasta consultarla.

### Reproducción y ciclo de vida
Estados previstos: pendiente, buscando, descargando, listo, en_reproduccion, visto, expira, borrado, fallido, vigilando, fijado y cancelado.

Comportamiento objetivo:
- Reutilizar un archivo que ya esté en caché.
- Cuando una fuente autorizada permita descarga progresiva, empezar la reproducción cuando exista colchón suficiente y la transferencia vaya por delante del punto de reproducción.
- Registrar progreso. La propuesta inicial marca como visto al alcanzar el 90 % y programa el borrado 48 horas después.
- Al borrar el archivo temporal, conservar catálogo y metadatos.
- Limitar inicialmente la concurrencia a una transferencia y una reproducción simultáneas.
- No borrar nunca un archivo en reproducción ni uno cuya transferencia siga activa.

Los umbrales concretos de reproducción progresiva deberán verificarse con Jellyfin, el cliente y el formato de archivo; no se consideran garantizados por diseño.

### Política de almacenamiento
- Cuota inicial confirmada: 80 GB para el SSD de 1 TB.
- Al superar el 90 % de la cuota, expulsar por antigüedad (LRU) elementos vistos y no fijados.
- No borrar elementos en reproducción ni transferencias activas.
- El diseño original propone bloquear nuevas solicitudes si quedan menos de 15 GB libres; revisar ese umbral frente al espacio real y las necesidades de Windows/WSL antes de activarlo.
- Panel con ocupación, cuota, elementos en caché y acción Vaciar caché.
- Borrar la caché nunca elimina SQLite, perfiles, catálogo ni metadatos.

## 3. Descubrimiento, solicitudes y cola

Prioridades propuestas:
- P0: petición confirmada desde el chat.
- P1: petición desde una ficha o elemento fijado.
- P2: descubrimiento/relleno automático opcional.

El descubrimiento, si se habilita, debe tener límites configurables, presupuesto por ciclo, deduplicación, idempotencia, criterios de calidad y modo de simulación. Por defecto enriquece metadatos y novedades; no inicia transferencias automáticas sin activación explícita.

La cola es durable en SQLite, nunca en memoria. Requisitos objetivo:
- Lease de 120 segundos y heartbeat cada 30 segundos.
- Recuperación de tareas cuando expire el lease.
- Reconciliación al arrancar con el cliente de transferencias, si está configurado.
- Backoff exponencial.
- Tras agotar intentos, estado vigilando con comprobaciones periódicas y motivo visible.
- Reactivar una tarea vigilada si vuelve a existir una fuente autorizada.
- Lista de espera con estado, motivo, intentos, próxima comprobación, Reintentar y Quitar.

Los intervalos y máximos de intentos del diseño original deben implementarse como configuración y probarse; no basta con tener columnas de lease.

## 4. Chat integrado

Intenciones previstas: buscar_y_encolar, consultar_disponibilidad, borrar, pausar y saludo.

Flujo:
1. Extraer título y año.
2. Resolver con TMDB y desambiguar cuando sea necesario.
3. Presentar tarjeta de confirmación con póster y datos.
4. Solo tras confirmar, crear solicitud P0.
5. Informar brevemente del estado real.
6. Si no se resuelve, pedir aclaración y sugerir coincidencias.
7. Si no hay fuente autorizada, explicarlo y, si procede, dejarlo en vigilancia.

Parser determinista por patrones y búsqueda difusa; un modelo local opcional puede ayudar con frases raras, pero nunca será obligatorio. El chat no podrá modificar ajustes. Historial separado por perfil.

## 5. Arquitectura y datos previstos

Entidades de la visión completa: usuario, perfil, ajuste, pelicula, serie, temporada, episodio, genero, persona, reparto, archivo_cache, solicitud, descarga, mensaje_chat, log_agente, fuente_indexer y exclusion.

Componentes:
- PWA: Next.js, React y TypeScript, navegación espacial, manifest, service worker y modo standalone.
- API: FastAPI + SQLModel + SQLite; autenticación, perfiles, catálogo, chat, cola, almacenamiento y ajustes.
- Worker separado con APScheduler; tareas largas fuera del proceso HTTP.
- Jellyfin: biblioteca y reproducción; VIEWTV no implementará un motor propio.
- TMDB: metadatos y atribución.
- Prowlarr y cliente de transferencias: adaptadores opcionales solo para fuentes y contenido autorizados.
- Bazarr: posible integración futura para subtítulos.
- Notificaciones dentro de la app; Telegram solo si se configura expresamente y de forma segura.

## 5.1 Fuentes e indexers — diseño pendiente y límites

Esta sección define una arquitectura futura para consultar catálogos Torznab compatibles, exclusivamente cuando las fuentes estén autorizadas para el contenido solicitado (por ejemplo, material propio, con licencia de distribución o de dominio público). No se configurarán ni documentarán listas de sitios cuyo propósito sea localizar copias no autorizadas de obras protegidas.

### Adaptador

- Mantener una única implementación de cliente/adaptador **Torznab genérico**, reutilizable para servicios compatibles como Prowlarr o Jackett.
- La URL base, ruta Torznab, credencial API y categorías serán configuración del servidor; no se codificarán credenciales ni URLs concretas en el frontend.
- La API y el worker consultan el adaptador desde el backend. La PWA nunca se conecta directamente a Prowlarr/Jackett ni recibe sus claves.
- No asumir que un indexer existe por aparecer en una guía o en otra instalación. Durante la implementación se comprobará el catálogo real expuesto por cada instancia y se documentarán únicamente los indexers que estén presentes y habilitados, junto con su tipo y resultado de prueba.
- La compatibilidad Torznab no implica que una fuente sea legal, fiable ni adecuada: cada fuente requiere revisión de autorización, términos y alcance del contenido.

### Normalización y filtros

- La aplicación consumirá la respuesta estructurada Torznab; **no parseará HTML ni automatizará páginas web**.
- Normalizar resultados a un modelo interno común antes de mostrarlos.
- Los filtros posteriores a la respuesta podrán incluir número de seeders, idioma/pista de audio declarada, perfil de calidad y tamaño máximo. Los valores ausentes o no verificables se mostrarán como desconocidos, no se inferirán.
- Los filtros son criterios de selección, no una verificación de derechos. Antes de crear una solicitud o iniciar una transferencia deberá existir una fuente y un elemento autorizados.

### Resiliencia y administración

- Un error HTTP 429/503 o un timeout marcará temporalmente la fuente como no disponible durante 30 minutos (valor inicial configurable).
- El fallo de una fuente no abortará la búsqueda global: se devolverán los resultados parciales y el estado de las fuentes fallidas.
- Panel de administración con estado por fuente, última comprobación, último error y un interruptor para habilitar/deshabilitar cada fuente.
- Aplicar límites de tiempo, concurrencia y reintentos; no repetir inmediatamente una fuente en periodo de enfriamiento.
- No se considerará implementado hasta disponer de pruebas para respuestas válidas, resultados parciales, rate limit, servicio no disponible, timeout, interruptor y recuperación tras el periodo de enfriamiento.

### Estado

Diseño documentado; **no implementado ni validado**. Prowlarr y Jackett no están instalados/configurados en el entorno actual. La futura verificación de catálogo se hará solo con fuentes autorizadas y no se presupone ningún nombre de indexer.

## 6. Diseño visual

Referencia: fondo #0B0B0F, acento #E50914, tipografía Inter, diseño escalable desde 1920×1080, tarjetas redondeadas, transiciones breves, foco de mando muy visible, navegación por flechas/Enter/Atrás, respeto a prefers-reduced-motion y contraste legible.

## 7. Estado real — actualizado el 4 de noviembre de 2026

### Hecho y comprobado
- [x] Repositorio privado wizzadrds/viewtv creado y clonado.
- [x] Windows 11 con WSL2 y Ubuntu 24.04 instalado.
- [x] Docker Desktop y Docker Compose instalados e integrados con Ubuntu.
- [x] docker run hello-world funciona.
- [x] Estructura inicial del proyecto y servicios API/worker en Compose.
- [x] API FastAPI con endpoint de salud; responde correctamente.
- [x] SQLite con SQLModel y migración Alembic inicial aplicada (0001_initial).
- [x] Modelos iniciales Perfil, Medio y Solicitud.
- [x] Campos de lease en Solicitud: locked_by, locked_until y heartbeat.
- [x] Operaciones iniciales de cola: reclamación exclusiva, renovación, finalización, fallo/reintento y recuento por estado.
- [x] Worker APScheduler separado, conectado a la base de datos y mostrando recuentos. Todavía no procesa solicitudes ni transferencias.
- [x] Autenticación con PIN hasheado con Argon2, JWT en cookie HttpOnly, logout, endpoint de perfil y límite inicial de intentos.
- [x] Perfiles Adultos e Infantil creados.
- [x] Login probado correctamente para ambos perfiles.
- [x] Suite backend: 14 pruebas superadas en la ejecución local del 4 de noviembre de 2026 (`pytest`: 14 passed; una advertencia deprecada de Starlette/httpx, no bloqueante).
- [x] Ruff: `ruff check app tests` devolvió `All checks passed!` el 4 de noviembre de 2026.
- [x] GitHub Actions Backend CI: run `41836114618` completado con `success` para el commit `5cf444f` (pruebas y Ruff).
- [x] Docker Compose levantado; API healthy y worker Up. /health responde y /auth/me sin sesión devuelve 401.
- [x] docs/plan-operativo.md creado en la rama de trabajo.
- [x] Jellyfin instalado como servidor en Windows y accesible en http://localhost:8096.
- [x] Confirmado que todavía no hay archivos multimedia ni bibliotecas Jellyfin.
- [x] Carpetas `C:\\VIEWTV\\media`, `cache`, `data` y `backups` creadas y accesibles desde Windows y WSL (`/mnt/c/VIEWTV`).
- [x] Caché de Docker trasladada del volumen nombrado al directorio `C:\\VIEWTV\\cache`, montado en `/cache` para API y worker; escritura comprobada en ambos contenedores.
- [x] API saludable tras el cambio; `/health` respondió HTTP 200.
- [x] SQLite sigue en el volumen `viewtv_viewtv_data`; archivo `viewtv.db` comprobado y migración `0001_initial (head)` confirmada.
- [x] `docker inspect` confirmó que API y worker comparten el bind mount de `C:\\VIEWTV\\cache` en `/cache` y el volumen persistente `viewtv_viewtv_data` en `/data`.
- [x] Volumen antiguo `viewtv_viewtv_cache` eliminado después de verificar que ningún contenedor lo utilizaba; `docker volume ls` confirmó que solo queda `viewtv_viewtv_data`.
- [x] Reinicio limpio comprobado con `docker compose down` y `docker compose up -d` (sin `-v`): API `healthy` y worker arrancado.
- [x] Persistencia tras el reinicio comprobada: Alembic `0001_initial (head)`, 2 perfiles conservados en SQLite y `/health` HTTP 200.
- [x] Commit `922b4c00157772207d6656af24231affd8e550af` publicado en `feature/fase-1-backend-base`; GitHub Actions Backend CI finalizó con `success` (run 11).

### En curso o parcial
- [ ] Fase 1: API, modelos, migración, cola inicial, autenticación, Compose y CI están en el repositorio; GitHub Actions Backend CI del commit `922b4c0` terminó correctamente. Falta comprobar un arranque limpio siguiendo README y completar revisión de seguridad/configuración y recuperación. No marcar fase completa aún.
- [ ] Jellyfin: servidor instalado y accesible, pero no hay usuario de servicio, API key, carpetas, bibliotecas ni conexión desde la API VIEWTV.
- [ ] Almacenamiento: caché ya montada en `C:\\VIEWTV\\cache` para API y worker; falta implementar la cuota/evicción y confirmar la ruta compartida de `media` con Jellyfin. El volumen Docker antiguo de caché ya fue eliminado.
- [ ] Documentación: existe el plan operativo; falta enlazar esta especificación y el plan desde README.

### Pendiente, por orden recomendado

#### Revisión de seguridad/configuración (actualizada el 4 de noviembre de 2026)

- [x] Corregir los alias de configuración para que `VIEWTV_ENV` y `VIEWTV_TIMEZONE` se lean realmente desde el entorno.
- [x] Retirar de `.env.example` `API_HOST` y `VIEWTV_LOG_LEVEL`, que no tenían consumidor en el código.
- [x] Limitar `JWT_EXPIRE_MINUTES` a valores entre 1 y 10.080 minutos (7 días).
- [x] Añadir una prueba para los nombres documentados de las variables de entorno.
- [x] Ejecutar localmente la suite y Ruff con estos cambios; comprobar CI: 14 pruebas superadas, Ruff limpio y GitHub Actions correcto para `5cf444f`.
- [ ] Revisar rate limit: actualmente el almacenamiento por defecto de SlowAPI es local al proceso; no equivale a un contador compartido entre varias réplicas ni persiste reinicios.
- [x] Comprobar la configuración efectiva: `AUTH_COOKIE_SECURE` no está definido y el valor por defecto del código es `false`; aceptable para HTTP local. Antes de acceso mediante HTTPS debe configurarse `true`.
- [x] Comprobar sin revelar el secreto que `JWT_SECRET` tiene al menos 32 caracteres.
- [x] Crear copia de SQLite con la API online backup, guardarla en `C:\\VIEWTV\\backups` y verificar el archivo copiado: `PRAGMA integrity_check=ok`, 2 perfiles y migración `0001_initial`.
- [x] Restauración aislada del backup: contenedor temporal `viewtv-restore-test`, base montada en solo lectura, API en `127.0.0.1:8001` con `/health` HTTP 200; integridad `ok`, 2 perfiles y migración `0001_initial`. Contenedor temporal eliminado. No se modificó la base activa.
- [ ] Programar la ejecución diaria del backup y validar su operación continuada; el script y la retención ya están implementados, pero todavía no hay tarea programada.

#### A. Cerrar fase 1
1. [x] Verificar que el commit y la rama remota contienen los últimos cambios; la copia local se actualizó con `git pull --ff-only` hasta el commit `2be846a`.
2. [x] Revisar GitHub Actions: runs 17 y 18 completados con `success`.
3. [x] Ejecutar reinicio limpio de los servicios sin borrar volúmenes; comprobar API, migración y persistencia de perfiles.
4. Revisar variables de entorno, secretos, límites de red y migraciones (pendiente).
5. [x] Las pruebas unitarias existentes cubren recuperación de leases caducados al reclamar, backoff exponencial y agotamiento de intentos; se añadieron casos para lease caducado en el límite de intentos y para impedir que un worker antiguo renueve o complete su lease. Pendiente: decidir e implementar recuperación/watchdog periódico al arrancar cuando exista un procesador real; el worker actual solo informa del estado.
6. [x] Actualizar README y documentación con el estado real; registrar también la ejecución local de 13 pruebas y Ruff.
7. Solo entonces declarar fase 1 terminada.

#### B. Jellyfin y fase 2
1. Decidir mantener Jellyfin nativo en Windows o migrarlo a Docker; por ahora no migrar sin motivo.
2. Definir carpetas persistentes y cómo compartirlas con Jellyfin y Docker.
3. Crear usuario de servicio Jellyfin con privilegios mínimos y API key.
4. Añadir credenciales al .env local sin compartirlas ni subirlas.
5. Implementar cliente Jellyfin real en backend y probar conectividad desde el contenedor API.
6. Importar biblioteca en modo solo lectura y sincronizar IDs, títulos, tipos, años, sinopsis, géneros e imágenes.
7. Definir TMDB v3, atribución y política para no duplicar metadatos.
8. Implementar endpoints de catálogo y vistas de inicio/detalle.
9. Probar reproducción de un archivo de prueba propio o autorizado.

#### C. Hardware, almacenamiento y red
1. Confirmar espacio real del SSD y política de 80 GB.
2. Comprobar suspensión/hibernación y cierre de tapa.
3. Decidir Ethernet o Wi-Fi y reservar IP local cuando proceda.
4. Definir firewall LAN y nombre local para el televisor.
5. Investigar Quick Sync Intel; no usar NVENC.
6. Verificar reproducción con formato objetivo 1080p H.264/AAC antes de añadir transcodificación.

#### D. Fases 3 y 4 — Solicitudes, transferencias y caché
1. Implementar adaptadores para fuentes autorizadas.
2. Integrar cliente de transferencias solo cuando exista una fuente legal configurada.
3. Implementar procesador real del worker con leases, heartbeat, reconciliación e idempotencia.
4. Gestionar una transferencia y una reproducción simultáneas al inicio.
5. Implementar disponibilidad progresiva con pruebas reales de buffering.
6. Implementar estados del archivo, progreso de visionado, borrado programado y protección de archivos activos.
7. Implementar política LRU, elementos fijados, freno por espacio libre y panel de almacenamiento.
8. Implementar lista de espera, reintentos y vigilancia.

#### E. Fase 5 — Chat
1. Crear historial persistente por perfil.
2. Implementar parser determinista, resolución TMDB y desambiguación.
3. Añadir tarjetas de confirmación.
4. Permitir que el chat cree únicamente solicitudes P0 tras confirmación.
5. Implementar respuestas basadas en resultados reales y estado de vigilancia.
6. Añadir rate limit y pruebas.

#### F. Fase 6 — PWA y televisor
1. Crear frontend Next.js/React/TypeScript.
2. Diseñar catálogo y fichas con el estilo acordado.
3. Implementar navegación espacial con mando, teclado y Atrás.
4. Crear manifest, service worker, instalación y modo standalone.
5. Implementar reconexión automática y estado Servidor apagado.
6. Probar TV Bro, cruceta, Enter, Atrás, dictado por voz y favoritos en Fire TV.
7. Añadir notificaciones y pulido visual/accesibilidad.

#### G. Validación final y mantenimiento
- Arranque desde cero siguiendo README.
- Solicitud de contenido de prueba autorizado disponible y reproducción.
- Solicitud no disponible y estado de vigilancia.
- Caída del worker y recuperación sin duplicados.
- Prueba de cuota y expulsión LRU.
- Borrado de caché sin pérdida de catálogo.
- Pruebas con mando en televisor.
- Copias de seguridad de SQLite y secretos fuera del portátil, en ubicación segura.
- Revisión periódica de dependencias y fuentes autorizadas.

## 8. Diferencias respecto al planteamiento inicial

- El planteamiento inicial describía un host Linux con GPU NVIDIA/NVENC. El entorno real confirmado es Windows 11 + WSL2 Ubuntu 24.04 y GPU Intel integrada. No instalar Linux nativo ni configurar NVENC por inercia; evaluar Quick Sync.
- El planteamiento inicial decía que Jellyfin, Prowlarr y qBittorrent ya funcionaban. En el entorno real, Docker y VIEWTV están activos; Jellyfin se acaba de instalar en Windows; Prowlarr y qBittorrent no están instalados; no hay biblioteca multimedia.
- La automatización técnica se limitará a contenido propio, autorizado o de dominio público.
- El equipo no estará encendido permanentemente. El sistema debe recuperarse cuando se encienda; las tareas deben tolerar reinicios y leases vencidos.

## 9. Próximo paso inmediato

1. Enlazar este documento y docs/plan-operativo.md desde README.
2. Verificar CI y cerrar fase 1.
3. Acordar la ruta compartida de almacenamiento y el modo de instalación de Jellyfin.
4. Crear usuario de servicio/API key de Jellyfin y comenzar el cliente de solo lectura de la fase 2.



## 10. Validación de copia de seguridad y restauración aislada (4 de noviembre de 2026)

- Se creó una copia coherente de `/data/viewtv.db` usando `sqlite3.Connection.backup()` desde el contenedor API, sin detener servicios ni modificar la base activa.
- Archivo guardado en `C:\\VIEWTV\\backups` (88 KB en la comprobación).
- Se copió el archivo guardado de nuevo a una ruta temporal del contenedor y se abrió como base independiente.
- Verificaciones: `PRAGMA integrity_check` devolvió `ok`; se leyeron los 2 perfiles; `alembic_version` devolvió `0001_initial`.
- Restauración aislada: el backup se montó en solo lectura en un contenedor temporal independiente. La API arrancó y `/health` devolvió HTTP 200 en `127.0.0.1:8001`; `PRAGMA integrity_check` devolvió `ok`, se leyeron los 2 perfiles y Alembic indicó `0001_initial`.
- El contenedor `viewtv-restore-test` se eliminó tras la prueba. La base activa y su volumen no se tocaron.
- Alcance: backup, copia, lectura y arranque de API aislada verificados. No se ha hecho una restauración sobre producción ni se ha probado el procedimiento completo de recuperación del host. Pendiente automatizar, definir retención y documentar/ensayar recuperación operativa.


### Automatización de backup — ejecución manual real validada; programación pendiente (4 de noviembre de 2026)

- Se añadió `backend/scripts/backup_db.py` con SQLite Online Backup API, origen en solo lectura, comprobación de integridad y publicación atómica.
- Retención configurable mediante `BACKUP_RETENTION_DAYS` (30 días por defecto); la limpieza solo afecta a nombres `viewtv-*.db` y solo se ejecuta tras crear correctamente una copia nueva.
- Compose monta `/mnt/c/VIEWTV/backups` en `/backups` dentro de API. No se monta en worker y no se toca el volumen `viewtv_viewtv_data`.
- Pruebas unitarias añadidas para copia, integridad, retención, rechazo de motores no SQLite y fallo de origen.
- [x] Cambios sincronizados; API recreada con el bind mount `/backups`; suite local: 19 pruebas superadas y Ruff limpio.
- [x] Copia real generada por el script: `viewtv-20261104-133925.db` (90.112 bytes; aprox. 88 KB) en `C:\\VIEWTV\\backups`.
- [x] Verificación independiente de esa copia: `PRAGMA integrity_check=ok`, 2 perfiles y migración `0001_initial`.
- [ ] Configurar y probar la programación diaria en el Programador de tareas de Windows; revisar también reintentos/registro de fallos. Hasta entonces, la copia está implementada y probada manualmente, pero no automatizada por horario.


### Resultado de la primera ejecución real del script (4 de noviembre de 2026)

El usuario ejecutó `docker compose exec -T api sh -c 'cd /opt/viewtv/backend && python scripts/backup_db.py'` desde Ubuntu/WSL. El script informó de la creación y verificación de `/backups/viewtv-20261104-133925.db` (90.112 bytes) y cero copias antiguas eliminadas. El archivo apareció en `/mnt/c/VIEWTV/backups/`. Una comprobación independiente sobre ese archivo devolvió integridad `ok`, 2 perfiles y versión `0001_initial`. La copia anterior también permanece intacta. Por tanto, el proceso de backup manual y la lectura de la copia están validados; la tarea diaria de Windows sigue pendiente.


### Lanzador de backup Windows/WSL validado (4 de noviembre de 2026)

- Se añadió `scripts/backup-daily.sh` para ejecutar la secuencia de Compose/health/backup directamente dentro de Ubuntu 24.04.
- `scripts/backup-daily.ps1` llama al script Bash mediante `wsl.exe --exec /bin/bash`, evitando el problema de interpretación del bloque multilínea anterior.
- Prueba real desde PowerShell invocado en WSL: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\\VIEWTV\\scripts\\backup-daily.ps1'`.
- Resultado correcto al primer intento: la API estaba activa, se creó y verificó `/backups/viewtv-20261104-134904.db` (90.112 bytes) y PowerShell recibió `Backup VIEWTV completado correctamente.`.
- [x] Lanzador PowerShell/Bash validado manualmente.
- [ ] Tarea diaria del Programador de tareas de Windows aún no creada ni probada; registro y comportamiento tras suspensión/reinicio pendientes. Por tanto, no considerar todavía activo el backup diario automático.


### Estado final de la programación diaria del backup (4 de noviembre de 2026)

- [x] Tarea `VIEWTV - Backup diario` creada en la Biblioteca del Programador de tareas de Windows.
- [x] Desencadenador diario configurado a las 03:00 (hora local de Madrid).
- [x] Acción PowerShell apunta a `C:\\VIEWTV\\scripts\\backup-daily.ps1`; ejecución solo con la sesión del usuario iniciada.
- [x] Prueba manual desde el Programador: última ejecución `04/11/2026 15:10:24`, resultado `0`.
- [x] Archivo producido por esa ejecución: `C:\\VIEWTV\\backups\\viewtv-20261104-141027.db`, 90.112 bytes.
- [x] Próxima ejecución informada por Windows: `05/11/2026 03:00:00`.
- Resultado: la automatización diaria está configurada y una ejecución real desde el Programador ha generado el backup esperado. Pendiente de seguimiento: comprobar la ejecución de las 03:00 del día siguiente y realizar en otro momento una prueba completa de recuperación del host. Si el portátil está apagado no puede ejecutar la tarea; la recuperación de una ejecución omitida depende de que Windows vuelva a arrancar y procese la tarea pendiente.


## 5.2 Integración Jellyfin — implementación inicial y validación pendiente

- La API del contenedor se autenticó correctamente contra Jellyfin nativo en Windows: HTTP 200, servidor `LAPTOP-VIEWTV`, versión `12.4.0`, usando la cabecera `Authorization: MediaBrowser Token=...`. La clave se guarda solo en `.env` local.
- Se añadieron ajustes de URL, clave y timeout, cliente HTTP de solo lectura y endpoints protegidos por sesión VIEWTV: `GET /jellyfin/status` y `POST /jellyfin/catalog/sync`.
- La sincronización consulta páginas de `/Items` para `Movie,Series` y persiste metadatos en `medio`: ID Jellyfin, tipo, título, sinopsis, año, géneros y rutas relativas de imágenes. No descarga ni almacena archivos de vídeo ni copia la clave a la base de datos.
- La implementación reutiliza el esquema existente, por lo que no añade migración en esta iteración. Se añadieron pruebas unitarias del cliente y del upsert.
- **Pendiente de validar:** tests/Ruff/CI, reconstrucción de la API con la nueva dependencia, llamada autenticada a los endpoints VIEWTV y sincronización con biblioteca Jellyfin poblada. La instalación actual aún no tiene bibliotecas ni medios, así que no se debe interpretar una sincronización vacía como fallo de autenticación.


### Validación real de la integración Jellyfin (4 de noviembre de 2026)

- [x] Inicio de sesión VIEWTV con el perfil Adultos: HTTP 200.
- [x] `POST /jellyfin/catalog/sync` con sesión autenticada: HTTP 200.
- [x] Respuesta de la API: `{"estado":"sincronizado","elementos_procesados":0}`.
- [x] Conectividad autenticada desde el contenedor API al servidor Jellyfin nativo Windows: `LAPTOP-VIEWTV`, versión `12.4.0`.
- El resultado de cero elementos es esperado: las bibliotecas `Películas` y `Series` están creadas, pero sus carpetas todavía no contienen archivos.
- Alcance de la validación: autenticación, conexión y ejecución del endpoint de sincronización verificadas. Quedan pendientes la importación con medios reales, paginación de un catálogo poblado, servicio de imágenes/carátulas y reproducción.


### Proxy de carátulas y fondos Jellyfin — implementación inicial

- Se añade el endpoint autenticado `GET /jellyfin/media/{media_id}/images/{image_kind}` (`primary` o `backdrop`). El cliente web solicita la imagen a VIEWTV; el backend consulta Jellyfin con su clave API privada y retransmite el contenido.
- El endpoint solo sirve imágenes asociadas a registros existentes en el catálogo y con imagen declarada en la sincronización. No funciona como proxy de URLs arbitrarias.
- Controles iniciales: máximo 10 MiB, MIME permitido JPEG/PNG/WebP/GIF, rechazo de formatos no permitidos, `nosniff` y caché privada de 1 hora.
- Pruebas añadidas: autenticación VIEWTV obligatoria, respuesta de bytes de imagen, cabeceras de seguridad, imagen ausente, autenticación MediaBrowser al upstream y rechazo de contenido no-imagen.
- Pendiente: ejecutar suite/Ruff/CI en el entorno del proyecto y probar con una película o serie real con carátula. No afirmar que la PWA ya muestra carátulas: el frontend todavía no está implementado.


### Validación local del proxy de imágenes (4 de noviembre de 2026)

- [x] 28 pruebas locales superadas; Ruff sin errores; CI verde.
- [x] API reconstruida y `/health` responde HTTP 200.
- [x] Petición al proxy sin sesión rechazada con HTTP 401.
- [x] Sesión Adultos válida; `/jellyfin/status` responde HTTP 200 y confirma servidor `LAPTOP-VIEWTV`, versión `12.4.0`.
- [x] Petición autenticada de imagen devuelve HTTP 404 porque el catálogo aún no contiene el ID local solicitado (la sincronización procesó cero elementos). Es el resultado esperado con las bibliotecas vacías.
- [ ] Descarga real de carátula/fondo desde Jellyfin pendiente de incorporar un medio propio o autorizado y sincronizarlo. El endpoint no está aún validado con bytes procedentes de un servidor Jellyfin real.


### API de catálogo para la PWA (4 de noviembre de 2026)

- [x] Implementado `GET /jellyfin/catalog` con autenticación de perfil.
- [x] Filtro opcional por tipo (`pelicula` o `serie`), paginación (`limit` 1–100, `offset` >= 0), total y orden alfabético por título.
- [x] Respuesta limitada a metadatos necesarios para la interfaz; las imágenes apuntan al proxy privado VIEWTV. No se filtran identificadores internos de Jellyfin ni claves API.
- [x] Añadidas pruebas de paginación, filtro, campos de imagen ausentes, validación de parámetros y rechazo sin sesión.
- [x] CI en GitHub Actions: 32 pruebas superadas y Ruff sin errores (commit `f024662864ba8833859e5e1049b882d06e22d896`).
- [ ] Actualizar la rama local y ejecutar la suite/Ruff en WSL.
- [ ] Verificación funcional con catálogo poblado pendiente de incorporar un medio propio o autorizado en Jellyfin y sincronizarlo.
- [ ] Verificación funcional con catálogo poblado pendiente de incorporar un medio propio o autorizado en Jellyfin y sincronizarlo.
