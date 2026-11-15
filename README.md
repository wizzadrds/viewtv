# VIEWTV

Aplicación multimedia doméstica autohospedada, con una experiencia PWA en español de España, diseñada para Android TV y Fire TV y manejable mediante mando a distancia.

VIEWTV separa el catálogo y los metadatos persistentes de los archivos multimedia temporales. Utiliza Jellyfin como servidor de biblioteca y reproducción, y contempla un flujo de solicitudes y transferencias controlado desde una API y un worker independiente.

**Estado del proyecto:** fase 1 cerrada. Fase 2 en curso, con sus cuatro primeros entregables cerrados. El siguiente trabajo previsto es implementar el procesador de solicitudes en el worker.

Consulta [`docs/ESTADO.md`](docs/ESTADO.md) para conocer el estado actualizado y el siguiente paso autorizado.

## Objetivos

- Interfaz doméstica en español, optimizada para pantallas de televisión.
- Perfiles protegidos mediante PIN.
- Catálogo y metadatos persistentes, independientes de la caché temporal de vídeo.
- Integración con Jellyfin para consultar la biblioteca y reproducir contenido.
- API con FastAPI, SQLModel y SQLite.
- Worker independiente y cola durable para procesar trabajos.
- Integración con Jackett mediante un adaptador Torznab genérico.
- Integración con qBittorrent para transferencias controladas.
- PWA instalable, con navegación espacial y soporte para mando a distancia.

Las funcionalidades descritas como objetivos no deben interpretarse como implementadas. El estado de cada entrega y sus validaciones se recoge en la documentación del proyecto.

## Documentación

### Estado y planificación

- [Estado actual del proyecto](docs/ESTADO.md)
- [Plan y entregables de fase 2](docs/FASE-2.md)
- [Contexto técnico y decisiones vigentes](docs/CONTEXTO.md)

### Diseño y operación

- [Arquitectura técnica](docs/arquitectura.md)
- [Plan operativo y entorno](docs/plan-operativo.md)
- [Especificación funcional e historial](docs/especificacion-y-estado.md)

### Revisiones e integraciones

- [Revisión de implementación](docs/REVISION-IMPLEMENTACION.md)
- [Procedimiento y estado del backup](docs/backup-operativo.md)
- [Integración y reproducción con Jellyfin](docs/reproduccion-jellyfin.md)

Antes de modificar código, revisa el estado actual, las decisiones vigentes y el entregable correspondiente. Actualiza la documentación cuando completes un hito.

## Arquitectura

| Componente | Tecnología | Responsabilidad |
| --- | --- | --- |
| Interfaz | Next.js, React y TypeScript | PWA, catálogo y navegación |
| API | FastAPI y SQLModel | Autenticación, catálogo y solicitudes |
| Persistencia | SQLite | Perfiles, metadatos y estado de trabajos |
| Procesamiento | Worker independiente | Ejecución de tareas fuera del ciclo HTTP |
| Biblioteca y reproducción | Jellyfin | Gestión de biblioteca y reproducción |
| Fuentes autorizadas | Jackett y Torznab | Consulta estructurada de fuentes |
| Transferencias | qBittorrent | Gestión de transferencias autorizadas |

La base de datos y los datos persistentes deben mantenerse separados de la caché de vídeo. La cuota inicial prevista para esta caché es de **80 GB**, configurable.

La aceleración de vídeo adoptada es Intel Quick Sync (QSV), no NVIDIA NVENC. Su funcionamiento efectivo debe validarse en el entorno.

## Entorno de desarrollo

Entorno documentado:

- Windows 11.
- WSL2 con Ubuntu 24.04.
- Docker Desktop y Docker Compose.
- Repositorio ubicado en el sistema de archivos Linux de WSL, por ejemplo `~/projects/viewtv`.

### Arranque del entorno base

Desde Ubuntu (WSL), en la raíz del repositorio:

```bash
cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

La API se publica inicialmente para acceso local en:

```text
http://localhost:8000/health
```

Para consultar los registros:

```bash
docker compose logs -f api worker
```

Para detener los servicios:

```bash
docker compose down
```

**Precaución:** no ejecutes `docker compose down -v` como operación rutinaria. La opción `-v` puede eliminar volúmenes persistentes, incluida la base de datos.

La configuración efectiva de los servicios, los montajes y las migraciones debe comprobarse en el entorno antes de realizar operaciones de mantenimiento.

Si se habilita el acceso desde un televisor por la LAN, habrá que configurar expresamente la publicación de la API y el cortafuegos de Windows para limitar el acceso a la red doméstica. No abras puertos en el router ni expongas el servicio directamente a Internet.

## Configuración y secretos

1. Copia `.env.example` a `.env` al preparar un entorno nuevo.
2. Sustituye los valores de ejemplo por credenciales y valores locales seguros.
3. Conserva los secretos exclusivamente en la configuración local.
4. No subas `.env`, contraseñas, PIN, tokens, cookies ni claves API al repositorio.
5. No compartas archivos de configuración privados ni bases de datos locales.

## Fuentes y derechos

Las integraciones de consulta y transferencia se utilizarán exclusivamente con contenido propio, autorizado o de dominio público.

- Jackett se consulta mediante Torznab estructurado.
- No se implementará parseo HTML ni automatización de páginas web.
- TMDB aporta metadatos, no archivos de vídeo.
- La compatibilidad técnica de una fuente no acredita los derechos sobre su contenido.

## Desarrollo

El trabajo se organiza por fases y entregables. La planificación vigente está en [`docs/FASE-2.md`](docs/FASE-2.md).

La rama de trabajo actual es `inventario-trabajo-local`. No se debe cambiar de rama, publicar cambios ni integrar trabajo en `main` sin autorización expresa.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo [`LICENSE`](LICENSE).
