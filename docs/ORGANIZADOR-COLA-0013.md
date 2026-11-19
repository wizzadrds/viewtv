# VIEWTV — Cola recuperable de organización (versión 0013, SOLO DESARROLLO)

Fecha: 19 de noviembre de 2026.

> **NO DESPLEGADA.** La instalación real sigue en API/worker `0012`, SQLite
> Alembic `0012_inicio_torrent`, PWA real en `127.0.0.1:3000`.
> El iniciador de torrents continúa **desactivado** y el verificador activo.
> No usar `alembic upgrade head` en la base real todavía.

## Qué se ha implementado

- Migración **`0013_cola_organizacion`** basada en `0012_inicio_torrent`.
- Seis columnas nuevas en `descarga`: `organizacion_estado`,
  `organizacion_locked_by`, `organizacion_locked_until`,
  `organizacion_disponible_desde`, `organizacion_intentos` y
  `organizacion_ultimo_error`.
- **La migración deja todas las descargas históricas en `no_requerida`**
  de forma segura; no crea automáticamente operaciones sobre archivos antiguos.
- Cuando una descarga llega por las rutas existentes de verificación a
  `estado_verificacion=verificada`, se marca su organización como
  `pendiente` de forma atómica. Si falla la verificación, no se activa.
- `app.organization_queue` reclama un trabajo con transacción
  `BEGIN IMMEDIATE` y lease de **180 segundos**; se requiere estado
  `completada`, progreso 100 %, verificación correcta y estado
  `pendiente`.
- Un segundo worker no puede reclamar un lease vigente. Un worker viejo no
  puede confirmar, aplazar o marcar revisión después de perder su lease.
- Hasta **3 intentos**. Un error temporal libera el lease y aplaza 60,
  120 o hasta 1800 segundos. En el tercero, la operación pasa a
  `requiere_revision`. Si el worker cae repetidamente y el tercer lease
  expira, pasa a revisión en la siguiente inspección, sin emitir un cuarto
  intento automático.
- Los errores persistentes son **códigos predefinidos**, no texto libre:
  `comunicacion`, `archivo_invalido`, `espacio_insuficiente`,
  `origen_cambio`, `otro`, además de `lease_agotado`.
  No guardar rutas, URL, PIN, claves ni mensajes de herramientas en esos campos.
- La función `confirm_organization` solo registra un resultado bajo un
  lease propio vigente. **No comprueba el disco:** un ejecutor futuro deberá
  validar todo antes de llamarla.

## Lo que NO se ha hecho

- **No hay ningún consumidor de esta cola en `worker/main.py`.**
  No se ha activado una bandera de organización ni se han cambiado montajes
  de medios a lectura/escritura.
- **No se han copiado, movido, renombrado o borrado archivos reales.**
  El planificador de `docs/ORGANIZADOR-SEGURO-PLAN.md` sigue siendo
  de solo lectura y los tests usan exclusivamente ficheros temporales.
- No se ha actualizado la base de datos real de `0012` a `0013`,
  ni se han sustituido los contenedores o activado torrents.

## Validación

- Pruebas específicas de cola: **28 correctas**. Cubren exclusión,
  recuperación tras caducidad, worker antiguo, reintentos, estado de revisión,
  codificación de errores, elegibilidad y verificación satisfactoria o fallida
  tanto con lease como con la ruta de compatibilidad.
- Migración **`0012 → 0013 → 0012` ensayada dentro de Docker con
  `viewtv:predeploy-0013-dev` sobre una COPIA temporal** del respaldo real
  post-despliegue de 0012. `PRAGMA integrity_check=ok`, sin errores de
  claves foráneas, se conservaron 2 perfiles, 1 solicitud y 0 descargas.
  El respaldo original fue verificado por SHA-256 antes y después.
- Suite completa backend: **375 pruebas aprobadas**, 2 avisos de deprecación
  conocidos. Ruff limpio en los archivos intervenidos.

## Siguientes pasos OBLIGATORIOS antes del primer movimiento real

1. Ejecutar copias **solo en sandbox**: abrir orígenes sin seguir symlinks,
   comprobar identidad del torrent, hash, tag, carpeta, tamaños y cambios
   entre verificación y lectura.
2. Planificar staging en la biblioteca de destino con control de espacio,
   escritura por mínimos permisos, fsync y publicación **sin sobrescritura**,
   tratando colisiones e interrupciones de forma idempotente.
3. Renovar leases/heartbeat durante copias grandes; no confirmar éxito
   desde un lease caducado. Después de una respuesta ambigua, conciliar
   el estado del disco ANTES de reintentar.
4. Probar múltiples vídeos, temporadas, subtítulos, títulos duplicados,
   cierres abruptos del proceso y permisos Windows/WSL.
5. Preparar y comprobar una biblioteca temporal de prueba y aprobación
   expresa para habilitar escritura confinada a `Peliculas`/`Series`.
   **El origen de los torrents NO se borra.**
6. Exponer estados de organización en la PWA con aislamiento por perfil,
   sin rutas internas, y planificar escaneo/reproducción Jellyfin.
7. Antes de desplegar `0013`: nuevo backup de producción,
   ensayo de migración/rollback sobre copia actualizada, tests finales y
   revisión humana de logs/configuración. Mantener flags de inicio y
   organización desactivados inicialmente.

**Este hito aporta durabilidad y control de concurrencia, NO el ejecutor.**

## Avance posterior: ejecutor aislado de copia

Se ha añadido un prototipo `worker/organization_copy_sandbox.py`, **solo para
`/tmp`**, que copia y publica en staging con protección contra enlaces y
sobrescrituras. Tiene **22 pruebas específicas** y la suite general alcanza
**397 pruebas aprobadas**. **No se conecta aún a esta cola ni a producción**.
Ver [ORGANIZADOR-COPIA-SANDBOX.md](ORGANIZADOR-COPIA-SANDBOX.md).

## Mejora de concurrencia: renovación de leases (desarrollo)

La función `renew_organization_lease` permite extender una reclamación de
organización **solo mientras sigue vigente**, por parte del mismo worker.
Se ejecuta en una transacción exclusiva con las mismas condiciones de
estado/verificación que la reclamación inicial. Los nuevos leases se limitan
a **1–900 segundos**, nunca se acorta el vencimiento anterior y un worker
antiguo, una tarea ya no verificada o un lease expirado no pueden renovarse.

La renovación es una herramienta de la cola, **no un heartbeat activo**:
el ejecutor real deberá llamarla periódicamente mientras realiza copias
grandes, y abortar o conciliar si pierde la reserva. No habilita por sí
sola operaciones sobre bibliotecas reales.

Validación posterior: **39 tests específicos de la cola**, más los tests
de copia aislada; **408 tests backend aprobados**, dos avisos de
compatibilidad conocidos, Ruff limpio. Migración real **sigue en 0012**.

## Nueva integración en sandbox (posterior a renovación de lease)

La coordinación entre cola, planificador y copiador **ya existe solo
para pruebas** en `worker/organization_runner_sandbox.py`. No se ha
activado en `worker/main.py` ni en la instalación `0012`.
La suite completa alcanza **422 pruebas aprobadas**. Ver el alcance
y los límites en [ORGANIZADOR-ORQUESTACION-SANDBOX.md](ORGANIZADOR-ORQUESTACION-SANDBOX.md).
