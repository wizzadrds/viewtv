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
- El volumen antiguo `viewtv_viewtv_cache` aún no se ha eliminado. No borrarlo hasta confirmar el estado del repositorio local y que ningún contenedor lo usa.
- La API quedó `healthy`, `/health` devolvió HTTP 200 y el worker permaneció en ejecución tras aplicar el nuevo montaje.

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
