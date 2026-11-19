# VIEWTV — Orquestación de organización en sandbox (desarrollo 0013)

Fecha: 19 de noviembre de 2026.

**ESTADO: SOLO PRUEBAS. NO DESPLEGADO NI HABILITADO EN PRODUCCIÓN.**

La instalación real sigue usando API/worker `viewtv:predeploy-0012-release`
y SQLite Alembic `0012_inicio_torrent`; la PWA real continúa en
`http://127.0.0.1:3000`. El inicio automático de torrents permanece
desactivado. No se han modificado descargas, medios, volúmenes ni permisos.

## Funcionalidad añadida

Se incorpora `worker/organization_runner_sandbox.py` con
`run_one_sandbox_organization(engine, sandbox_root, worker_id, source_provider)`:

1. **Rechaza primero cualquier carpeta que no sea un sandbox marcado
   explícitamente bajo `/tmp`**. El rechazo ocurre *antes* de reclamar
   trabajo en SQLite; una ruta como `/media` está prohibida.
2. Reclama exclusivamente una descarga marcada como completa,
   verificada y pendiente de organización, usando la cola durable `0013`.
3. Vuelve a consultar la descarga y su solicitud, obtiene los archivos
   ficticios mediante un proveedor **inyectado exclusivamente en las
   pruebas** y construye el plan con las validaciones de rutas existentes.
4. Renueva su lease vigente antes y durante la copia (callback por bloque
   de hasta 1 MiB, y antes de publicar). Una reserva perdida o una
   verificación revocada impiden la publicación o confirmación.
5. Utiliza el copiador de sandbox con staging, verificación SHA-256 del
   origen y destino, y publicación exclusiva sin sobrescribir.
6. Renueva nuevamente el lease y **solo entonces** registra `organizada`.
   Si la confirmación no tiene éxito, informa `lease_perdido` y no emite
   otra copia automáticamente.
7. Ante un error conocido de ruta, formato, colisión o contenido, trata de
   registrar `requiere_revision` con un código seguro, sin almacenar
   rutas ni excepciones sensibles. Si perdió el lease no puede cambiar
   el estado a espaldas de otro worker.
8. Ante una interrupción imprevista, deja el lease y el staging como
   testimonio. Cuando caduca, el siguiente intento **no reutiliza ni
   borra esos restos**: va a revisión manual sin duplicar contenido.

**El proceso no está importado desde `worker/main.py`**. No consulta
qBittorrent real y no tiene acceso autorizado a los directorios reales.

## Pruebas realizadas

- `backend/tests/test_organization_runner_sandbox.py`: **14 pruebas
  nuevas** de orquestación, incluyendo:
  - Ejecución completa con SQLite de pruebas y conservación de originales.
  - Rechazo de `/media` y de sandbox sin marcador antes de reclamar trabajo.
  - Archivos ajenos y destinos/staging ya existentes.
  - Corte durante la copia y corte **después de la publicación atómica**,
    antes de actualizar la base de datos.
  - Pérdida de lease durante la copia.
  - Dos workers concurrentes sin publicar dos veces.
  - Revocación de la verificación durante la selección de archivos.
  - Tareas no verificadas y proveedor de archivos inválido.
- `backend/tests/test_organization_copy_sandbox.py`: las 22 pruebas
  existentes siguen pasando, ahora con callback opcional de progreso
  que permite renovar el lease antes de publicar.
- **Suite backend completa: 422 pruebas aprobadas**, 2 advertencias
  de dependencias conocidas. Ruff limpio y `git diff --check` correcto.
- No se ha ejecutado ningún test sobre archivos reales del usuario.

## Límites de seguridad y siguientes requisitos

**No habilitar el sistema sobre las bibliotecas de producción en esta
fase.** El copiador solo opera bajo `/tmp` con un marcador específico y
archivos de prueba de hasta 32 MiB. La integración de cola y copia
actual es deliberadamente independiente de Docker Compose real.

Para la ejecución sobre ficheros autorizados faltan:
- Verificar **en el instante de la copia** la identidad exacta del torrent
  qBittorrent, su hash, etiqueta de propiedad, ruta de guardado y
  pertenencia a la solicitud. No tocar ningún torrent preexistente ajeno.
- Autenticidad del contenido originalmente verificado: el SHA-256 de la
  copia garantiza la fidelidad de transferencia, **no sustituye** la
  verificación de identidad de qBittorrent ni de procedencia.
- Trabajar con ficheros multimedia grandes en el volumen Windows
  únicamente después de probar permisos, espacio disponible, enlaces,
  semántica real de `renameat2` y confinamiento estricto de escritura.
- Heartbeat periódico y renovación fuera de los bloques de copia cuando
  existan operaciones de I/O bloqueantes o publicaciones lentas.
- Política conservadora de conciliación de staging y resultado ambiguo;
  recuperación idempotente sin borrar el origen.
- Soportar temporadas existentes, múltiples episodios y formatos reales
  sin colisiones, con pruebas en un volumen separado de demostración.
- Desplegar `0013` únicamente tras backup actualizado, ensayo de
  migración/restauración y autorización para los montajes necesarios.
- Escaneo Jellyfin, reproducción, comprobación de TV y documentación
  de rollback y mantenimiento.

Referencias: [planificador](ORGANIZADOR-SEGURO-PLAN.md),
[cola 0013](ORGANIZADOR-COLA-0013.md),
[copiador sandbox](ORGANIZADOR-COPIA-SANDBOX.md).

## Ampliación: validación simulada de identidad qBittorrent

El coordinador de pruebas ya admite un proveedor inyectado que usa el
**guard de identidad de solo lectura** antes de generar el plan. En la
simulación, un torrent propio puede llegar al estado `organizada`, un
torrent con etiqueta ajena o carpeta incorrecta pasa a revisión y un
fallo de comunicación previo al staging se aplaza sin escribir.

Esta protección **no se conecta al qBittorrent real** ni convierte
el runner de sandbox en un ejecutor de producción. Ver el nuevo documento
[ORGANIZADOR-QBITTORRENT-IDENTIDAD.md](ORGANIZADOR-QBITTORRENT-IDENTIDAD.md).

Suite completa posterior: **471 pruebas aprobadas**; Ruff sin errores.
