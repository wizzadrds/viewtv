# Worker de VIEWTV

Proceso independiente encargado de ejecutar tareas de la cola durable sin
depender de que la API o la interfaz web mantengan una petición abierta.

## Estado implementado

- Sondeo de la cola cada 10 segundos.
- Procesamiento de una solicitud como máximo por ciclo.
- Identificador único por proceso worker.
- Reclamación de solicitudes mediante leases.
- Búsqueda en Jackett mediante Torznab XML.
- Persistencia de resultados utilizables y deduplicados.
- Transición a `esperando_seleccion` cuando hay resultados.
- Transición a `sin_resultados` cuando no hay opciones utilizables.
- Registro de errores y reintentos mediante la cola durable.
- Liberación del lease al finalizar la búsqueda.

## Flujo de selección

La selección de torrents es manual:

1. El worker reclama una solicitud pendiente.
2. Consulta Jackett.
3. Guarda los resultados utilizables.
4. Libera el lease y deja la solicitud esperando selección.
5. El usuario selecciona explícitamente un resultado.

El procesador de búsquedas no envía torrents a qBittorrent.

## Pendiente

- Endpoint y flujo completo de selección, si aún no están integrados.
- Envío del resultado seleccionado a qBittorrent.
- Seguimiento persistente del progreso de las descargas.
- Recuperación y reconciliación de transferencias tras reinicios.
- Pruebas de integración del worker con servicios reales.

No debe considerarse implementado el ciclo completo de descarga hasta cerrar
esas tareas.

## Configuración

El worker comparte la configuración y el volumen de datos de la API.
La base de datos se gestiona mediante las migraciones de Alembic ejecutadas
por el servicio API antes de que el worker arranque.

Consulta:

- [docs/ESTADO.md](../docs/ESTADO.md)
- [docs/FASE-2.md](../docs/FASE-2.md)
- [docs/arquitectura.md](../docs/arquitectura.md)
