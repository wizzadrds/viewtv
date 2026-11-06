# VIEWTV

Aplicación multimedia doméstica autohospedada, con interfaz PWA optimizada para Android TV y Fire TV.

> **Estado actual:** API, worker y autenticación operativos; integración Jellyfin validada con un medio real, catálogo sincronizado y proxy de carátulas comprobado. Primera etapa del backend de reproducción añadida en una rama de trabajo: negociación Direct Play y proxy HTTP con soporte Range; aún pendiente validación local y conexión del reproductor PWA. La primera interfaz PWA con Next.js/React/TypeScript ya está implementada en `frontend`: selección de perfil/PIN, catálogo, filtros, búsqueda, detalles y navegación espacial inicial. Falta instalar dependencias y validar el frontend en navegador y Fire TV. Consulta el estado detallado en la documentación del proyecto.

## Objetivos

- Interfaz tipo centro multimedia, en español (España), navegable con mando a distancia.
- Perfiles protegidos mediante PIN.
- Catálogo y metadatos persistentes, independientes de la caché temporal de vídeo.
- Integración con Jellyfin para consultar la biblioteca y reproducir contenido.
- API con FastAPI, SQLModel y SQLite.
- Trabajador separado para tareas asíncronas y una cola duradera con concesiones temporales (leases).
- PWA instalable y adaptable a pantallas de televisión.

## Documentación principal

- [Plan operativo y decisiones del entorno](docs/plan-operativo.md)
- [Especificación funcional, progreso y tareas pendientes](docs/especificacion-y-estado.md)
- [Arquitectura técnica](docs/arquitectura.md)
- [Procedimiento y estado del backup diario](docs/backup-operativo.md)
- [Implementación y estado de reproducción Jellyfin](docs/reproduccion-jellyfin.md)

Antes de continuar una tarea, revisar estos documentos para conocer las decisiones ya tomadas y el estado real. Actualizarlos al completar hitos.

## Arquitectura prevista

| Componente | Tecnología prevista | Responsabilidad |
| --- | --- | --- |
| Interfaz | Next.js, React, TypeScript | PWA, navegación espacial y experiencia de TV |
| API | FastAPI, SQLModel | Autenticación, catálogo, solicitudes y configuración |
| Persistencia | SQLite | Perfiles, catálogo, solicitudes y estado de tareas |
| Worker | Python + APScheduler | Procesamiento y recuperación de tareas |
| Reproducción | Jellyfin | Biblioteca y reproducción multimedia |
| Fuentes externas | Adaptadores configurables | Metadatos y fuentes autorizadas |

La base de datos y sus volúmenes persistentes no deben estar dentro del directorio de caché. La caché de vídeo será temporal y tendrá una cuota inicial de **80 GB**, configurable mediante variables de entorno.

## Desarrollo local

El entorno actual es Windows 11 con WSL2 (Ubuntu 24.04) y Docker Desktop con integración WSL habilitada. Trabaja desde el sistema de archivos Linux de WSL (por ejemplo, `~/projects/viewtv`) para evitar penalizaciones de rendimiento de montajes bajo `/mnt/c`.

### Arranque del entorno base

Desde Ubuntu (WSL), en la raíz del repositorio:

```bash
cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

La API queda disponible inicialmente solo en el propio equipo: `http://localhost:8000/health`. La primera ejecución aplica las migraciones de SQLite automáticamente. Los servicios `api` y `worker` se ejecutan por separado y comparten volúmenes distintos para datos persistentes y caché. El worker todavía no procesa solicitudes ni transferencias reales.

Para ver los registros: `docker compose logs -f api worker`. Para detener los servicios: `docker compose down`. No uses `docker compose down -v`, porque eliminaría los volúmenes persistentes.

Si más adelante se desea acceder desde el televisor por la LAN, habrá que configurar el bind de la API y el cortafuegos de Windows para permitir solo la red doméstica. No abras el puerto en el router ni publiques el servicio en Internet.

## Configuración y secretos

1. Copia `.env.example` a `.env` cuando prepares un entorno nuevo.
2. Sustituye los valores de ejemplo por valores locales seguros.
3. No subas nunca `.env`, contraseñas, PIN, tokens ni claves API al repositorio ni los compartas por chat.

## Fuentes y derechos

Los adaptadores de búsqueda/transferencia se utilizarán únicamente con contenido propio, autorizado o de dominio público. TMDB aporta metadatos, no archivos de vídeo.

## Fases

1. Estructura del repositorio, configuración, persistencia, cola inicial, autenticación y CI.
2. Integración con Jellyfin y catálogo de solo lectura.
3. Solicitudes y procesamiento de cola para fuentes autorizadas, con reproducción.
4. Ciclo de vida de caché, cuotas y lista de espera.
5. Asistente conversacional con confirmación explícita.
6. PWA instalable, navegación con mando y pulido.

## Licencia

Pendiente de definir por el propietario del proyecto.
