# VIEWTV — avance de salida: estado de cola y conectividad real

**Fecha:** 20 de noviembre de 2026.
**Objetivo:** sacar una versión utilizable de VIEWTV antes de ampliar
el organizador. Documento ligado al
[plan maestro de salida](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Verificado en el equipo del usuario

La API restaurada en el hito anterior seguía saludable con
`viewtv:predeploy-0012-release`; frontend, worker, Jellyfin y
FlareSolverr continuaban activos. Se repitieron las 10
comprobaciones GET de la interfaz, proxy, perfiles, protección
de sesión y salud de Jellyfin, sin credenciales.

### Inventario agregado de SQLite

El script nuevo
`scripts/viewtv_release_inventory_readonly.py` se ejecutó en
contenedor efímero con **red deshabilitada**, volumen
`viewtv_viewtv_data` montado **solo lectura**, usuario sin
privilegios, y `PRAGMA query_only=ON`.

Resultado, sin leer ni mostrar títulos, nombres, magnet, URLs,
hashes ni texto de error original:

| Indicador | Resultado |
|---|---:|
| Perfiles activos | 2 |
| Medios registrados | 2 |
| Medios disponibles en Jellyfin | 1 |
| Solicitudes registradas | 1 |
| Solicitudes fallidas | 1 |
| Solicitudes fallidas con intentos agotados | 1 |
| Resultados de búsqueda guardados | 0 |
| Descargas creadas | 0 |

El error registrado de la solicitud antigua se clasifica como
**fallo de comunicación con el proveedor Jackett**, sin exponer
la cadena original. No se ha reintentado ni modificado.

### Comprobación de integraciones ahora mismo

Se ejecutaron por **stdin** en el worker activo dos scripts
nuevos de consulta estrictamente de lectura. No se copiaron
scripts al contenedor, no se abrieron secretos ni se mostraron
configuraciones sensibles.

- `scripts/viewtv_jackett_probe_readonly.py`:
  `JackettClient.get_indexers()` consulta el endpoint
  `t=indexers` (sin búsqueda). Resultado: **OK, un
  indexador configurado**. No valida todavía que una búsqueda
  futura devuelva resultados.
- `scripts/viewtv_qbit_probe_readonly.py`:
  `QBittorrentClient.version()` consulta solamente
  **GET /api/v2/app/version**. Resultado: **OK**.
  No se consultaron archivos o torrents ni se realizó POST.
- Inicio automático de descargas: `VIEWTV_ENABLE_DOWNLOAD_START=false`;
  no se ha cambiado.

**Interpretación limitada:** el error de comunicación de la
solicitud antigua no se reproduce en estas consultas de estado,
pero eso **no prueba** todavía la búsqueda Torznab con un
título real, la selección, el alta de torrents ni la reproducción
autenticada. No declarar terminado el flujo.

## Código y pruebas del hito

Todos los ficheros del diagnóstico son nuevos, salvo la actualización
del plan maestro. No se modificó código de negocio ni Docker:

- `scripts/viewtv_release_inventory_readonly.py`:
  agregados SQL y clasificación sin filtración de datos personales.
- `scripts/viewtv_jackett_probe_readonly.py`:
  lectura del estado de indexadores con salida saneada.
- `scripts/viewtv_qbit_probe_readonly.py`:
  lectura del endpoint de versión, sin torrents.
- `backend/tests/test_release_diagnostics_readonly.py`:
  cinco pruebas sobre SQLite **en memoria** y mensajes de error
  sintéticos, incluyendo ausencia de detalles sensibles.
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`:
  actualizado con el inventario, el estado real de integraciones
  y la norma de documentar cada avance en GitHub.

Validación del hito:
- 5 pruebas nuevas: **correctas**, exit 0 (0,10 s).
- Ruff `check` y `format --check`: **correctos**.
- Smoke de aplicación: **10/10 correctas**.
- Suite completa backend: **620 tests correctos**, exit code 0
  (43,56 s), con dos avisos de deprecación conocidos,
  sin caché pytest ni generación de bytecode.

### Respaldo del documento existente

Antes de editar el plan maestro se generó:

`/home/viewtv/viewtv-backups/plan-salida-inventario-pre-20261120-183122.tar.gz`

SHA-256:
`6724a8f396557c07d21312d24fe5462e372aed63f034d86e59c9b8adc4b3c0d2`

`tar -tzf` verificó exactamente un archivo:
`docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`.

Los cuatro scripts/pruebas nuevos y este informe no tenían
versión previa que respaldar.

## Próxima acción imprescindible para la primera versión

1. Confirmar **inicio y cierre de sesión en el navegador** con el
   PIN del usuario, que no se comparte con el asistente.
2. Comprobar catálogo y reproducción de un medio ya existente
   con el usuario autenticado, sin modificar archivos.
3. Realizar una búsqueda de prueba autorizada desde la interfaz
   y verificar que el indexador devuelve resultados. La solicitud
   antigua fallida **no** se reabre automáticamente.
4. Verificar selección y seguimiento de la descarga; activar
   cualquier función que inicie torrents solamente mediante
   ensayo explícitamente autorizado, con copia de seguridad
   y reversión.
5. Integrar solo la organización indispensable para publicar
   un archivo de prueba autorizado, después de cerrar las
   pruebas de los pasos anteriores.

**Límites:** no se ha completado el login, una búsqueda real,
una descarga real ni una publicación a Jellyfin. Ninguna prueba
de conectividad reemplaza esas validaciones.

**Política Git:** cada avance se registra en el plan, informe
técnico, pruebas, commit español y push a
`viewtv-seguimiento-descargas-0012`. PR #2 permanece en borrador,
sin fusionar. No tocar torrents ni biblioteca sin autorización.
