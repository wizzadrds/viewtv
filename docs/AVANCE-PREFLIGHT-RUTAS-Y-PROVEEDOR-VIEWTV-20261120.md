# VIEWTV — comprobación real y de solo lectura de rutas y búsquedas

**Fecha:** 20-11-2026.
**Rama autorizada:** `viewtv-seguimiento-descargas-0012`.
**Objetivo:** identificar el siguiente bloqueo de salida de la aplicación
sin crear solicitudes, dar de alta torrents, iniciar transferencias ni
acceder a archivos multimedia privados.

**Plan:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Qué se ha comprobado en el equipo Windows

Se consultó **solo el metadato del propio directorio** mediante
`Get-Item -LiteralPath` sobre dos rutas fijas, sin enumerar hijos,
leer archivos, cambiar permisos ni crear carpetas:

- `C:\VIEWTV\media`
- `C:\VIEWTV\media\descargas_temporales`

El script versionado
`scripts/viewtv_windows_staging_preflight_readonly.ps1`
se ejecutó con PowerShell 5.1 y verificó:

```text
CHECK_PARENT_DIRECTORIO=True
CHECK_PARENT_REPARSE=False
CHECK_STAGING_DIRECTORIO=True
CHECK_STAGING_REPARSE=False
STAGING_PREFLIGHT=OK_SOLO_METADATA
```

Esto acredita **existencia, tipo directorio y ausencia de
ReparsePoint**, pero **no** demuestra los permisos del SID de
qBittorrent, un archivo descargado, rendimiento ni operaciones NTFS.

## Preferencias reales de qBittorrent: lectura sin revelar secretos

Se envió por stdin al worker activo
`scripts/viewtv_qbit_staging_probe_readonly.py`.
Usó la configuración existente sin imprimirla y consultó
**solo GET /api/v2/app/preferences**. La respuesta se clasificó
en memoria y no se mostraron URL, clave, otras preferencias,
nombres de torrents ni rutas privadas.

Resultado:

```text
QBIT_PREFERENCIAS=OK
RUTA_DEFECTO=IGUAL
RUTA_TEMPORAL=DISTINTA
USO_CARPETA_TEMPORAL=NO
```

La carpeta predeterminada de qBittorrent coincide con la carpeta
staging requerida por el worker. Hay otra ruta temporal configurada,
pero qBittorrent informa que **no está habilitada**. No se intentó
cambiar ninguna preferencia.

**Límite importante:** el worker envía un `savepath` explícito
al dar de alta un torrent; comprobar preferencias del servidor
no demuestra aún que un torrent real vaya a escribirse allí.
Tampoco se ha comprobado el acceso efectivo del proceso de
qBittorrent a los archivos; hace falta el ensayo autorizado.

## Búsquedas reales de Jackett, pero sin modificar la aplicación

Se ejecutó el script
`scripts/viewtv_jackett_search_probe_readonly.py` por stdin
dentro del worker. Consultó `JackettClient.search`
**solo mediante GET Torznab** con dos términos de ejemplo
que no son secretos ni solicitudes del usuario:

- Tipo `movie` y título **Big Buck Bunny** (cortometraje libre).
- Tipo `search` y término **ubuntu** (software libre).

Una consulta adicional previa del tipo `search` con
**Big Buck Bunny** también respondió sin error.

El script no imprime ningún título devuelto, URL de descarga,
magnet, hash, nombre de indexador, configuración ni respuesta XML.
Únicamente muestra si la búsqueda se ejecutó y la categoría del
número de resultados.

Resultado final:

```text
JACKETT_BUSQUEDA_MOVIE=OK
MOVIE_JACKETT_RESULTADOS_ENLACE=NO
MOVIE_JACKETT_RESULTADOS_RANGO=0
JACKETT_BUSQUEDA_SEARCH=OK
SEARCH_JACKETT_RESULTADOS_ENLACE=NO
SEARCH_JACKETT_RESULTADOS_RANGO=0
```

**Interpretación estricta:** el endpoint está accesible, la
autenticación configurada funciona y la respuesta pudo procesarse,
pero el indexador **no encontró resultados para esos términos**.
No basta para concluir que todo Jackett esté roto ni que
las búsquedas desde «Buscar y pedir» funcionen con títulos
reales. El estado del único indexador configurado se había
comprobado mediante GET en el avance anterior.

No se creó solicitud, no se eligió resultado, no se llamó a
qBittorrent con POST y no se consultaron torrents de otras personas.
No hubo cambios de Docker, SQLite, servicios Windows, ACL ni medios.

## Herramientas y salvaguardas que quedan en el repositorio

- `scripts/viewtv_windows_staging_preflight_readonly.ps1`: solo
  metadatos de los dos directorios fijos; salida sin nombres
  de archivos y exit 2 si falla la validación.
- `scripts/viewtv_qbit_staging_probe_readonly.py`: GET y comparación
  Windows con unidades absolutas; no acepta UNC, relativos
  ni segmentos `..` que pudieran ocultar un cambio de ruta.
  Una preferencia no comparable **no** se presenta como coincidente.
- `scripts/viewtv_jackett_search_probe_readonly.py`: dos consultas
  GET con términos de prueba públicos, resumen sin información de
  resultados ni errores de servidor.
- `backend/tests/test_release_provider_preflight_readonly.py`:
  **16 pruebas nuevas** con preferencias y resultados inventados,
  comparaciones de rutas, casos de error y prohibición de fuga
  de datos privados en los resúmenes.

Validación del hito:
- Script PowerShell 5.1: **correcto**, exit 0.
- 16/16 pruebas focales Python: **correctas**, exit 0.
- Ruff `check` y `format --check`: **correctos**.
- Smoke de aplicación API/interfaz/Jellyfin: **10/10 correcto**.
- Suite completa backend: **700 pruebas aprobadas**, exit code 0
  (110,40 segundos), con los dos avisos de deprecación ya conocidos
  de Starlette y sin escritura de caché ni bytecode.

## Copia de seguridad verificada

Antes de editar el **único archivo existente** afectado, el
plan maestro, se generó el archivo selectivo:

`/home/viewtv/viewtv-backups/rutas-proveedores-readonly-pre-20261120-203144.tar.gz`

SHA-256:

`7cb0b0998d2516b55a6d454e14ced3adeed08c948519fa5c076841f5ffe7d71e`

Se verificó `tar -tzf`: contiene **solo**
`docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`.
Los tres scripts, las pruebas y este informe son nuevos y no
tenían versión anterior que respaldar.

## Decisión para el siguiente hito de salida

Se elimina la incertidumbre del staging: carpeta existente,
sin redirección y preferencia por defecto de qBittorrent coincidente.
El **bloqueo pendiente de diagnóstico** es la obtención de
resultados desde el índice Jackett para una solicitud real:

1. Comprobar desde «Buscar y pedir» con un título autorizado
   si la solicitud cambia a `esperando_seleccion` o
   `sin_resultados`; no reabrir automáticamente la solicitud
   fallida antigua.
2. Si sigue sin resultados, revisar **en solo lectura** el estado
   y capacidades del indexador, sin modificar claves o
   descargar contenido ajeno.
3. Tras una selección legítima, ejecutar solo con autorización
   un alta detenida y después el inicio limitado a esa única ID,
   seguido de organización/publicación en Jellyfin.
4. Probar recuperación y reversión antes de declarar acabada
   la primera versión con organizador.

El inicio real sigue **desactivado** en producción:
`VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
`VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=""`,
`VIEWTV_ENABLE_DOWNLOAD_START=false`.

**Este hito no necesita despliegue:** solo añade herramientas de
lectura, tests y documentación al branch autorizado. El PR #2
permanece abierto en borrador, sin fusionar.
