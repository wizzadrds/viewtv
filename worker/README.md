# Worker de VIEWTV

Proceso independiente destinado a ejecutar tareas asíncronas sin depender de que la API o la interfaz web mantengan una petición abierta.

## Estado actual

El worker forma parte de la arquitectura del proyecto y la cola persistente dispone de mecanismos de leases y heartbeat. Sin embargo, el procesador del flujo de solicitudes y transferencias es el siguiente entregable de la fase 2 y todavía está pendiente.

No debe darse por implementada la recuperación integral de transferencias ni el procesamiento automático de solicitudes.

## Diseño previsto

El procesador deberá coordinar:

- La obtención segura de solicitudes pendientes.
- La adquisición y renovación de leases.
- La recuperación de trabajos abandonados o cuyo lease haya vencido.
- La consulta de fuentes autorizadas mediante Jackett y Torznab XML.
- La selección de resultados y la integración con qBittorrent.
- La actualización persistente de los estados de solicitudes y descargas.
- El tratamiento de errores, reintentos y reinicios.

Las responsabilidades y transiciones concretas deberán definirse antes de implementar el entregable.

## Planificación

La biblioteca o mecanismo de planificación del worker no debe considerarse una decisión definitiva por la mera presencia de APScheduler en documentación o dependencias anteriores.

El diseño técnico del procesador se revisará y acordará antes de modificar su implementación.

Consulta:

- [`docs/ESTADO.md`](../docs/ESTADO.md)
- [`docs/FASE-2.md`](../docs/FASE-2.md)
- [`docs/arquitectura.md`](../docs/arquitectura.md)
