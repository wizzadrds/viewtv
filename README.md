# VIEWTV

Aplicación multimedia doméstica autohospedada, con interfaz PWA optimizada para Android TV y Fire TV.

> **Estado:** inicio de la fase 1. La estructura y las decisiones de arquitectura se irán incorporando por fases; este repositorio todavía no representa una instalación funcional.

## Objetivos

- Interfaz tipo centro multimedia, en español (España), navegable con mando a distancia.
- Perfiles protegidos mediante PIN.
- Catálogo y metadatos persistentes, independientes de la caché temporal de vídeo.
- Integración con Jellyfin para consultar la biblioteca y reproducir contenido.
- API con FastAPI, SQLModel y SQLite.
- Trabajador separado para tareas asíncronas y una cola duradera con concesiones temporales (leases).
- PWA instalable y adaptable a pantallas de televisión.

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

El entorno de desarrollo objetivo es Windows 11 con WSL2 (Ubuntu 24.04) y Docker Desktop con integración WSL habilitada. Trabaja desde el sistema de archivos Linux de WSL (por ejemplo, `~/projects/viewtv`) para evitar penalizaciones de rendimiento de montajes bajo `/mnt/c`.

### Arranque del entorno base

Desde Ubuntu (WSL), en la raíz del repositorio:

```bash
cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

La API quedará disponible inicialmente solo en el propio equipo: `http://localhost:8000/health`. La primera ejecución aplica las migraciones de SQLite automáticamente. Los servicios `api` y `worker` se ejecutan por separado y comparten volúmenes distintos para datos persistentes y caché. El worker es todavía un esqueleto APScheduler; el procesamiento real de la cola se añadirá en la fase correspondiente.

Para ver los registros: `docker compose logs -f api worker`. Para detener los servicios: `docker compose down`. No uses `docker compose down -v`, porque eliminaría los volúmenes persistentes.

Si más adelante se desea acceder desde el televisor por la LAN, habrá que cambiar `API_BIND_ADDRESS` por la IP LAN del equipo y configurar el cortafuegos de Windows para permitir solo la red doméstica. No abras el puerto en el router ni publiques el servicio en Internet.

Consulta [docs/arquitectura.md](docs/arquitectura.md) para las decisiones iniciales.

## Configuración y secretos

1. Copia `.env.example` a `.env` cuando exista una configuración ejecutable.
2. Sustituye todos los valores de ejemplo por valores locales seguros.
3. No subas nunca `.env`, contraseñas, PIN, tokens ni claves API al repositorio.

El servicio se diseñará para uso doméstico en red local. No se debe publicar directamente en Internet ni abrir puertos del router como parte de la configuración inicial.

## Fuentes y derechos

Los adaptadores de búsqueda/descarga deberán utilizarse únicamente con contenido propio, autorizado o de dominio público. No se incluirán flujos orientados a localizar u obtener obras protegidas sin autorización.

## Fases

1. Estructura del repositorio, configuración, persistencia y CI.
2. Integración con Jellyfin y catálogo de solo lectura.
3. Solicitudes y cola duradera de tareas.
4. Ciclo de vida de la caché, cuotas y lista de espera.
5. Asistente conversacional con confirmación explícita.
6. PWA instalable, navegación con mando y pulido.

## Licencia

Pendiente de definir por el propietario del proyecto.
