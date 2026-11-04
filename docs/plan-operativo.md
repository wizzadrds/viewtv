# VIEWTV — Plan operativo y estado acordado

Este documento conserva las decisiones del proyecto y debe consultarse junto con `README.md` y `docs/arquitectura.md` antes de proponer nuevas tareas. Actualizarlo cuando cambie el estado.

## Reparto del trabajo

- **Usuario:** realiza instalaciones y configuraciones manuales en Windows, Ubuntu/WSL, Docker, Jellyfin y el televisor; ejecuta comandos y valida cada fase.
- **Asistente:** diseña e implementa VIEWTV, mantiene el código, documentación, pruebas, migraciones e integraciones, y guía las tareas manuales paso a paso.
- Indicar siempre dónde ejecutar cada instrucción: PowerShell, Ubuntu/WSL o interfaz web.
- Consultar este documento y el repositorio antes de preguntar decisiones ya respondidas. No dar una fase por terminada sin revisar sus pruebas y validación en TV cuando corresponda.

## Decisiones confirmadas

| Elemento | Estado |
| --- | --- |
| Repositorio | Privado: `wizzadrds/viewtv` |
| Rama de trabajo | `feature/fase-1-backend-base` |
| Equipo anfitrión | Windows 11; nombre comunicado: `LAPTOP-V2QSMC01` |
| Linux | Ubuntu 24.04 en WSL2; no hay Linux nativo instalado |
| Docker | Docker Desktop con integración WSL2; Compose funciona |
| SSD | 1 TB; cuota inicial de caché: **80 GB** |
| GPU | Intel integrada, no NVIDIA. No usar NVENC; investigar Quick Sync/QSV y verificar soporte antes de activarlo |
| Zona horaria | `Europe/Madrid` |
| Perfiles | Adultos e Infantil creados; inicio de sesión probado |
| Jellyfin | Instalado en Windows y accesible en `http://localhost:8096`; en la interfaz se ha visto el nombre `LAPTOP-VIEWTV` |
| Biblioteca multimedia | Todavía no hay archivos ni bibliotecas configuradas |
| Red | No abrir puertos en el router; v1 limitada a la red local |

No pedir ni pegar en el chat PIN, contraseñas, claves API, cookies, tokens ni el contenido de `.env`.

## 1. Equipo, almacenamiento y disponibilidad

### Almacenamiento confirmado (3 de noviembre de 2026)

- SSD anfitrión: unidad Windows `C:` (SSD de 1 TB).
- Carpetas creadas y verificadas desde Windows y WSL: `C:\\VIEWTV\\media`, `C:\\VIEWTV\\cache`, `C:\\VIEWTV\\data` y `C:\\VIEWTV\\backups`; en WSL están bajo `/mnt/c/VIEWTV/`.
- Jellyfin permanece instalado de forma nativa en Windows. La carpeta prevista para sus bibliotecas es `C:\\VIEWTV\\media`; todavía no hay bibliotecas ni archivos multimedia.
- Compose monta `C:\\VIEWTV\\cache` en `/cache` para los servicios `api` y `worker` mediante `/mnt/c/VIEWTV/cache`. Se verificó escritura desde ambos contenedores.
- La base de datos permanece en el volumen Docker `viewtv_viewtv_data`, montado en `/data`; `viewtv.db` existe y Alembic informa `0001_initial (head)`. No se ha movido a `C:\\VIEWTV\\data`.
- El volumen antiguo `viewtv_viewtv_cache` se eliminó el 3 de noviembre de 2026 tras comprobar que ningún contenedor lo utilizaba. Solo permanece `viewtv_viewtv_data`.
- La API quedó `healthy`, `/health` devolvió HTTP 200 y el worker permaneció en ejecución tras aplicar el nuevo montaje. `docker inspect` confirmó que API y worker comparten el mismo bind mount de caché y el volumen `viewtv_viewtv_data`.
- El 3 de noviembre de 2026 se ejecutó `docker compose down` seguido de `docker compose up -d` (sin `-v`): la API volvió a `healthy` y el worker arrancó. Después del reinicio, `alembic current` confirmó `0001_initial (head)`, la consulta SQLite confirmó 2 perfiles y `/health` respondió HTTP 200.

1. Confirmar el espacio real del SSD. Mantener 80 GB de caché para 1 TB; si el disco real fuese de 256 GB, usar 40 GB.
2. Elegir y documentar una ruta persistente de caché. No usar la raíz del SSD ni `/tmp`.
3. Separar estrictamente la caché temporal de SQLite, perfiles y metadatos persistentes.
4. Crear la carpeta y verificar permisos desde los servicios que la necesiten.
5. Decidir una ruta compartida coherente entre VIEWTV, Jellyfin y el cliente de transferencias que se habilite.
6. Comprobar suspensión, hibernación y comportamiento al cerrar la tapa. No asumir que WSL/Docker siguen trabajando si Windows suspende.
7. Preferir Ethernet cuando sea posible para la reproducción progresiva.

## 2. Sistema y Docker

- Mantener Windows 11 + WSL2 Ubuntu 24.04 + Docker Desktop.
- Ejecutar los comandos del proyecto desde `~/projects/viewtv` en Ubuntu, salvo indicación contraria.
- Verificar `docker compose version` y `docker compose ps` cuando se modifique el entorno.
- Mantener los datos persistentes y la caché en volúmenes separados.
- La integración WSL de Docker Desktop gestiona el acceso de Docker; no asumir que se necesita el grupo `docker` de una instalación Linux nativa.

## 3. Jellyfin

- Jellyfin es el servidor de biblioteca y reproducción; VIEWTV conserva su catálogo, perfiles, solicitudes y experiencia de usuario.
- VIEWTV consultará Jellyfin en modo de solo lectura para sincronizar películas, series, temporadas, episodios, identificadores, imágenes y metadatos.
- Crear un usuario de servicio con privilegios mínimos y una API key; guardarla solo en el entorno del servidor.
- Configurar bibliotecas de películas y series cuando estén definidas las carpetas de contenido.
- Decidir si se mantiene Jellyfin nativo en Windows o se migra a Docker. El plan inicial decía contenedor, pero la instalación actual es Windows; no cambiarla sin acordarlo.
- Si VIEWTV gestiona metadatos con TMDB, evitar duplicar descargas automáticas de metadatos en Jellyfin.
- No configurar NVENC en este equipo Intel. Investigar Quick Sync/QSV y comprobar compatibilidad real de hardware, controladores y contenedores.

## 4. Fuentes, metadatos y transferencias

- TMDB puede aportar metadatos; no proporciona los archivos de vídeo.
- Prowlarr puede actuar como gestor de fuentes configurables y qBittorrent como cliente de transferencias.
- Estas integraciones se implementarán únicamente para contenido propio, autorizado o de dominio público, respetando las condiciones de cada fuente.
- Para fuentes compatibles, la arquitectura prevista usa un único adaptador Torznab genérico, con credenciales solo en backend, normalización de resultados y sin parseo HTML. La lista real de fuentes se verificará en cada instancia; no se presupone el catálogo de Prowlarr/Jackett.
- Errores 429/503/timeout: enfriamiento inicial de 30 minutos por fuente, sin cancelar la búsqueda global; panel con estado y habilitación individual. Este comportamiento está especificado, pero aún no implementado.
- Filtros previstos sobre resultados estructurados: seeders, idioma/pista declarada, perfil de calidad y tamaño máximo. Estos filtros no sustituyen la comprobación de que el contenido está autorizado.
- No configurar fuentes cuyo propósito sea obtener obras protegidas sin autorización ni automatizar ese flujo.
- Prowlarr y qBittorrent aún no están instalados/configurados.
- Si se habilita qBittorrent para transferencias autorizadas: WebUI con credenciales fuertes, acceso LAN restringido, carpeta temporal definida y límites razonables de transferencia.
- Obtener TMDB API v3 si se decide usarlo; revisar atribución y términos. Guardar la clave únicamente en `.env`.

## 5. Red y seguridad

1. Para el acceso desde el televisor, reservar una IP DHCP o documentar una dirección estable.
2. Configurar un nombre local tipo `.local` solo tras probar resolución desde el Fire Stick.
3. Permitir los puertos necesarios en el firewall únicamente desde la LAN.
4. Mantener la API en localhost hasta que se necesite acceso desde la LAN.
5. No abrir puertos en el router ni publicar API, Jellyfin o paneles de administración en Internet en la v1.
6. Usar credenciales fuertes, privilegios mínimos y secretos fuera de Git.

## 6. Fire TV

- Probar TV Bro en el Fire Stick.
- Abrir una página local de prueba y verificar cruceta, foco, Enter y desplazamiento.
- Probar el dictado por voz del teclado del sistema.
- Guardar la dirección local de VIEWTV en favoritos.
- Validar cada fase relevante en el televisor, no solo en escritorio. Resolver problemas de mando antes del pulido final de la PWA.

## 7. Repositorio y configuración

- El repositorio privado está creado y clonado en WSL.
- Trabajar con ramas y commits pequeños.
- Usar `.env.example` como plantilla; nunca subir `.env`.
- Completar claves de Jellyfin, TMDB y servicios opcionales solo cuando estén instalados.
- La fase 1 ya comprobó que la tabla `solicitud` tiene `locked_by`, `locked_until` y `heartbeat`.
- No compartir PIN, claves API, contraseñas, cookies o tokens en conversaciones ni commits.

## 8. Fases de VIEWTV

1. Base del repositorio, Compose, configuración, SQLite, migraciones, cola durable y CI.
2. Integración Jellyfin de solo lectura, sincronización de catálogo y fichas.
3. Solicitudes, cola durable y reproducción mediante Jellyfin.
4. Ciclo de vida de caché, cuota de 80 GB, caducidad, expulsión y lista de espera.
5. Asistente conversacional determinista con desambiguación y confirmación explícita.
6. PWA instalable, navegación espacial con mando, notificaciones y pulido.

Revisar criterios de aceptación y pruebas antes de pasar a la siguiente fase.

## 9. Pruebas finales

Con contenido de prueba autorizado:
1. Levantar desde cero siguiendo el README.
2. Solicitar un elemento disponible y comprobar el flujo hasta la reproducción.
3. Solicitar uno no disponible y comprobar el mensaje y estado de vigilancia/lista de espera.
4. Detener el worker durante un trabajo y comprobar recuperación del lease.
5. Llenar la cuota de prueba y comprobar la expulsión según la política definida.
6. Borrar la caché y verificar que perfiles, catálogo y metadatos persisten.
7. Repetir pruebas principales con el mando del televisor.

## 10. Mantenimiento

- Revisar periódicamente las fuentes autorizadas y sus condiciones.
- Actualizar servicios y dependencias de forma controlada.
- Hacer copias de seguridad de la base de datos y de la configuración secreta fuera del portátil, en un destino seguro.
- No guardar secretos en el repositorio ni enviarlos por chat.

### Backup SQLite — procedimiento validado inicialmente (4 de noviembre de 2026)

- La base activa está en el volumen Docker `viewtv_viewtv_data`, ruta `/data/viewtv.db`; no está en `C:\\VIEWTV\\data`.
- Se validó una copia online mediante `sqlite3.Connection.backup()` desde el contenedor API. No hace falta parar API/worker y no se debe copiar el archivo SQLite activo con un `cp` ordinario mientras está en uso.
- La copia se guardó en `C:\\VIEWTV\\backups` (accesible desde WSL como `/mnt/c/VIEWTV/backups`).
- Se volvió a copiar el archivo de backup a una ruta temporal del contenedor y se abrió como base independiente. `PRAGMA integrity_check` devolvió `ok`, se leyeron los dos perfiles y la versión Alembic fue `0001_initial`.
- Restauración aislada verificada el 4 de noviembre de 2026: el archivo se montó en solo lectura en un contenedor temporal independiente; la API arrancó y `/health` devolvió HTTP 200 en `127.0.0.1:8001`. La comprobación SQLite devolvió integridad `ok`, 2 perfiles y Alembic `0001_initial`. El contenedor temporal se eliminó. No se modificó el volumen ni la base activa.
- Alcance: no se ha restaurado sobre producción ni ensayado la recuperación completa del host/servicios. No sobrescribir `/data/viewtv.db` para probar.
- Pendiente: programación diaria, supervisión/alerta de errores y procedimiento de recuperación operativa. Mantener al menos una copia adicional fuera del portátil para recuperación ante fallo del SSD.


### Automatización de backup SQLite — primera implementación (4 de noviembre de 2026)

- Añadido `backend/scripts/backup_db.py`: usa la Online Backup API de SQLite, abre el origen en modo solo lectura, valida `PRAGMA integrity_check` y publica el archivo con renombrado atómico solo después de validar.
- Nombre generado: `viewtv-AAAAMMDD-HHMMSS.db`.
- Retención inicial configurable mediante `BACKUP_RETENTION_DAYS` (30 días por defecto). Solo elimina archivos que coincidan con `viewtv-*.db`, y la limpieza se ejecuta después de crear correctamente el nuevo backup.
- Compose monta `C:\\VIEWTV\\backups` en `/backups` únicamente en el servicio API. No se monta sobre el volumen SQLite ni sobre la caché multimedia.
- Ejecución manual prevista desde Ubuntu/WSL: `docker compose exec -T api python scripts/backup_db.py`.
- Estado: código, pruebas y ejecución manual real verificados. El contenedor API tiene el montaje `/backups`; el primer backup generado por el script se verificó con SQLite. La programación diaria con el Programador de tareas de Windows sigue pendiente.


### Validación del script de backup en el entorno real (4 de noviembre de 2026)

- Se ejecutó desde Ubuntu/WSL, en el contenedor API: `cd /opt/viewtv/backend && python scripts/backup_db.py`.
- Resultado del script: backup creado y verificado en `/backups/viewtv-20261104-133925.db`, tamaño 90.112 bytes; backups antiguos eliminados: 0.
- El archivo apareció en el SSD anfitrión como `C:\\VIEWTV\\backups\\viewtv-20261104-133925.db` (aprox. 88 KB).
- Verificación independiente del archivo recién creado: `PRAGMA integrity_check=ok`, 2 perfiles y versión Alembic `0001_initial`.
- Se conserva también la copia anterior `viewtv-2026-11-04-141712.db`; ambas permanecen en la carpeta de backups.
- Conclusión: montaje, escritura, creación de copia online, integridad y lectura de la copia real están comprobados. La ejecución sigue siendo manual; no existe todavía una tarea diaria programada ni alerta de fallo.


### Lanzador para programación en Windows (4 de noviembre de 2026)

- Añadido `scripts/backup-daily.ps1` para invocarlo desde el Programador de tareas de Windows.
- El script llama a Ubuntu 24.04 en WSL como usuario `viewtv`, entra en `~/projects/viewtv`, levanta la API con Compose, espera hasta cinco minutos a que `/health` responda y ejecuta el script de backup dentro del contenedor API.
- Si WSL/Docker/Compose falla, reintenta hasta 10 veces con pausas de 60 segundos. Escribe un registro acumulado en `C:\\VIEWTV\\logs\\backup-daily.log`.
- El lanzador está añadido al repositorio, pero todavía no se ha ejecutado desde PowerShell ni se ha creado la tarea programada. Hay que validarlo manualmente antes de confiar en la programación.
- Configuración propuesta de la tarea: diariamente a las 03:00; activar «Ejecutar la tarea lo antes posible si se omitió el inicio programado» y «Activar el equipo para ejecutar esta tarea» si Windows ofrece esa opción. Un equipo apagado no puede hacer la copia hasta que vuelva a arrancar; la opción de inicio omitido permite recuperarla después.


### Prueba del lanzador Windows/WSL superada (4 de noviembre de 2026)

- Se separó la lógica Linux en `scripts/backup-daily.sh`; el lanzador `scripts/backup-daily.ps1` invoca ese archivo con `wsl.exe --exec /bin/bash`, evitando pasar un bloque multilínea por `bash -lc`.
- El archivo PowerShell se copia a `C:\\VIEWTV\\scripts\\backup-daily.ps1` para ejecutarlo desde una ruta nativa de Windows. La ruta UNC `\\\\wsl.localhost\\Ubuntu-24.04\\...` era visible con `Test-Path`, pero PowerShell no la aceptaba como argumento de `-File`.
- Ejecución real completada desde Ubuntu: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\\VIEWTV\\scripts\\backup-daily.ps1'`.
- Resultado: intento 1 correcto, API disponible, backup creado y verificado como `/backups/viewtv-20261104-134904.db` (90.112 bytes), mensaje final `Backup VIEWTV completado correctamente.`.
- Pendiente: crear y probar la tarea del Programador de tareas de Windows; comprobar que el log `C:\\VIEWTV\\logs\\backup-daily.log` se genera y definir alerta ante fallos. La programación diaria aún no está activa.


### Programación diaria de backup verificada en Windows (4 de noviembre de 2026)

- Creada en la Biblioteca del Programador de tareas la tarea `VIEWTV - Backup diario`, en la ruta raíz `\\`.
- Desencadenador diario configurado a las 03:00, zona horaria local de Windows (Europe/Madrid).
- Acción: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\\VIEWTV\\scripts\\backup-daily.ps1"`; directorio de inicio `C:\\VIEWTV\\scripts`.
- Configuración: ejecutar solo cuando el usuario haya iniciado sesión; no requiere privilegios elevados. En Condiciones se permite funcionar con batería y se marca «Activar el equipo para ejecutar esta tarea». En Configuración se habilita la ejecución a petición y la ejecución lo antes posible si se omitió el inicio programado; si ya hay una instancia, no iniciar otra.
- Prueba real desde el Programador: `LastRunTime=04/11/2026 15:10:24`, `LastTaskResult=0`. El archivo `C:\\VIEWTV\\backups\\viewtv-20261104-141027.db` apareció con 90.112 bytes y hora 15:10:27, coincidente con la ejecución.
- Comprobación final del horario: `NextRunTime=05/11/2026 03:00:00`.
- Conclusión: la tarea diaria está creada, el lanzador se ejecutó correctamente desde el Programador y se generó un archivo de backup real en el SSD. No equivale a una restauración completa del host. El portátil apagado no puede ejecutar la tarea; la reanudación desde suspensión depende de la configuración y capacidad del equipo. Conviene comprobar mañana que la ejecución programada dejó un nuevo archivo y que `LastTaskResult` sigue siendo 0.


### Integración Jellyfin — primera implementación (4 de noviembre de 2026)

- Se creó una clave API con nombre VIEWTV en el panel de Jellyfin y se guardó únicamente en el `.env` local; nunca se incorpora al repositorio.
- Prueba real desde el contenedor API contra `http://host.docker.internal:8096/System/Info`: HTTP 200, servidor `LAPTOP-VIEWTV`, versión `12.4.0`. Se verificó autenticación mediante `Authorization: MediaBrowser Token=...` sin imprimir la clave.
- En la rama `feature/fase-1-backend-base` se incorporó configuración `JELLYFIN_BASE_URL`, `JELLYFIN_API_KEY` y `JELLYFIN_TIMEOUT_SECONDS`; el ejemplo usa `host.docker.internal` porque Jellyfin está instalado nativamente en Windows y la API corre en Docker Desktop.
- Añadido cliente HTTP de solo lectura y rutas protegidas por sesión VIEWTV: `GET /jellyfin/status` y `POST /jellyfin/catalog/sync`. La sincronización pagina el endpoint `/Items`, limita los tipos a películas y series y hace upsert de título, sinopsis, año, géneros e identificadores de imágenes en `medio`. No descarga vídeos ni guarda la clave en los metadatos.
- No se requiere migración de SQLite para esta primera integración: se reutilizan los campos existentes de `medio` y su identificador Jellyfin único.
- Añadidas pruebas unitarias para autenticación MediaBrowser, parámetros de consulta y normalización/upsert de metadatos. Pendiente: ejecutar CI/pruebas en el entorno local, comprobar `/jellyfin/status` mediante sesión VIEWTV y probar sincronización con una biblioteca real. Actualmente Jellyfin todavía no tiene bibliotecas ni archivos multimedia, por lo que la primera sincronización real puede devolver cero elementos.
- Estado: implementación subida a la rama, pero no dar por validada hasta pasar pruebas y comprobar los endpoints en el contenedor.


### Integración Jellyfin — prueba local de catálogo superada (4 de noviembre de 2026)

- La API VIEWTV respondió HTTP 200 al inicio de sesión del perfil Adultos.
- La llamada autenticada `POST /jellyfin/catalog/sync` respondió HTTP 200 con `{"estado":"sincronizado","elementos_procesados":0}`.
- La prueba confirma el recorrido de autenticación VIEWTV → endpoint de sincronización → cliente Jellyfin → respuesta correcta. La conectividad y autenticación de la API contra Jellyfin ya se habían verificado desde el contenedor: servidor `LAPTOP-VIEWTV`, versión `12.4.0`.
- El recuento cero es coherente con el estado actual: las bibliotecas Jellyfin `Películas` y `Series` ya están creadas sobre `C:\\VIEWTV\\media\\Peliculas` y `C:\\VIEWTV\\media\\Series`, pero aún no contienen archivos multimedia.
- Alcance: no se ha probado todavía la importación de elementos reales, la paginación con una biblioteca poblada, la entrega de imágenes/carátulas ni la reproducción desde VIEWTV. La sincronización no implica que las vistas PWA estén implementadas.


### Proxy privado de imágenes Jellyfin — implementación subida, validación local pendiente

- Añadido `GET /jellyfin/media/{media_id}/images/{image_kind}`, protegido por la sesión de perfil VIEWTV. El identificador usado en la URL es el ID local del registro `medio`, no una ruta libre del servidor.
- Tipos permitidos: `primary` y `backdrop`; el backend construye la ruta Jellyfin a partir del ID guardado en catálogo. No acepta URLs externas ni rutas arbitrarias.
- El backend descarga la imagen con la clave MediaBrowser desde Jellyfin y devuelve los bytes a la PWA. La clave API nunca forma parte de la respuesta ni debe enviarse al navegador.
- Límite de tamaño: 10 MiB. Se aceptan JPEG, PNG, WebP y GIF; se rechazan HTML/SVG y otros tipos. La respuesta incluye `X-Content-Type-Options: nosniff` y caché privada de una hora.
- Añadidas pruebas para autenticación del endpoint, respuesta de imagen, ausencia de cabecera Authorization hacia el cliente, elemento sin imagen, cabecera de autenticación al servidor Jellyfin y rechazo de tipos no permitidos.
- Estado: código y pruebas añadidos a la rama. Pendiente de ejecutar pytest, Ruff, CI y probar con una carátula real en Jellyfin. Como las bibliotecas actuales están vacías, la prueba real de imagen requerirá añadir temporalmente un medio propio o autorizado.


### Proxy de imágenes — validación local de acceso (4 de noviembre de 2026)

- La suite local terminó con 28 pruebas superadas y Ruff sin errores; CI también finalizó correctamente.
- API reconstruida en Docker Compose y comprobada con `GET /health`: HTTP 200.
- Sin cookie de sesión, `GET /jellyfin/media/1/images/primary` devuelve HTTP 401, como exige el control de acceso.
- Con inicio de sesión del perfil Adultos, `GET /jellyfin/status` devuelve HTTP 200 y confirma Jellyfin `LAPTOP-VIEWTV`, versión `12.4.0`.
- Con sesión autenticada, la petición de imagen de prueba devuelve HTTP 404 `Elemento no encontrado`, esperado porque la sincronización anterior registró cero medios y no existe aún el ID local 1. No demuestra todavía la descarga de una imagen real.
- Pendiente: añadir un vídeo propio/autorizado a una biblioteca, ejecutar sincronización y probar una imagen primaria real (y fondo si existe).
