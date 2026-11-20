# VIEWTV — capacidades reales de Jackett y bloqueo de búsquedas

**Fecha:** 20-11-2026.
**Rama:** `viewtv-seguimiento-descargas-0012`.
**Plan:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Motivo

Tras estabilizar VIEWTV y preparar los permisos de alta e inicio
de una única descarga, el bloqueo de la primera versión sigue siendo
la validación de una búsqueda real que devuelva resultados.

El sondeo anterior comprobó GET Torznab de `Big Buck Bunny`
(película libre) y `ubuntu` (software libre): las dos consultas
respondieron sin errores, pero **con cero resultados**. No debemos
interpretar un HTTP 200 sin resultados como confirmación de que
el proveedor está funcionando para la búsqueda del usuario.

Se investigó si la API de VIEWTV estaba usando operaciones de
búsqueda que el único indexador configurado no admitiese.

## Resultado real, sin leer contenidos privados

El script `scripts/viewtv_jackett_capabilities_probe_readonly.py`
se ejecutó por stdin dentro del worker usando su configuración
existente. Consultó la lista Torznab `t=indexers` y un único
GET `t=caps` del indexador marcado como configurado.
El código solo emitió flags, sin identificadores, credenciales,
URLs, respuestas XML, títulos, hashes ni resultados torrent.

Resultado:

```text
INDEXADORES_ACTIVOS_RANGO=1
CAPS_ESTADO=OK
CAPS_GENERAL=SI
CAPS_GENERAL_Q=SI
CAPS_MOVIE=SI
CAPS_MOVIE_Q=SI
CAPS_TV=SI
CAPS_TV_Q=SI
```

Jackett enumera **654 indexadores disponibles en su catálogo**,
pero solo **uno configurado** en la instalación. Ese indexador
declara soporte Torznab para `search`, `movie-search` y
`tv-search`, incluido el parámetro de búsqueda por título `q`.
Eso coincide con el protocolo que implementa
`backend/app/jackett.py` y con los tipos
`movie`/`tvsearch` usados por `worker/processor.py`.

**Conclusión:** no hay evidencia de incompatibilidad de tipo de
búsqueda. No se modifica la API ni se añaden consultas duplicadas
de fallback sin prueba de necesidad.

El segundo script nuevo,
`scripts/viewtv_jackett_indexer_health_probe_readonly.py`,
intentó un GET a la ruta administrativa de estado del indexador.
Resultado: `JACKETT_ESTADO=NO_VERIFICABLE`.
Esa ruta no devolvió datos que permitieran acreditar el estado;
**no significa que el indexador esté inactivo**. El endpoint de
la interfaz de administración no debe equipararse con la API
Torznab pública, y no se debe esquivar su autenticación ni
consultar secretos para forzar la lectura.

El análisis **no** comprobó la sesión de la UI de Jackett ni
las pruebas que ofrece el panel de ese proveedor. Tampoco prueba
que haya contenido para los títulos consultados.

## Evidencias y herramientas añadidas

- `scripts/viewtv_jackett_capabilities_probe_readonly.py`:
  consulta únicamente GET; valida la ID antes de crear una
  ruta de URL y resume los `caps` sin publicar datos internos.
  Una respuesta XML desconocida/error no se interpreta como OK.
- `scripts/viewtv_jackett_indexer_health_probe_readonly.py`:
  intento read-only de clasificación de salud administrativa;
  informa solo `NO_VERIFICABLE` ante fallos de acceso/parsing,
  no revela mensajes de error, token o nombre del indexador.
- `backend/tests/test_release_jackett_caps_readonly.py`:
  **18 pruebas** sin red, con datos ficticios. Comprueban
  capacidades, parámetros `q`, XML erróneo, IDs con ruta
  peligrosa, solo GET, no exposición de claves, informe de
  salud ausente y saneamiento de mensajes internos.
- Actualizado
  `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`.

Los scripts se transmitieron por stdin a un proceso Python
dentro del **worker ya existente**, sin instalar nada,
reiniciar Docker, cambiar variables de entorno, ni crear
solicitudes o torrents. Los tests solo usan fixtures y
simulaciones sin red.

## Validación

- 18 pruebas focales: **aprobadas**, exit 0.
- Ruff `check` y `format --check`: **correctos**.
- Smoke read-only de interfaz, API, sesión, proxy y Jellyfin:
  **10/10 PASS**.
- Suite completa backend: **718 pruebas aprobadas**, exit code 0
  (86,58 s), con dos avisos de deprecación conocidos de Starlette.
- Inventario agregado SQLite posterior, montado **solo lectura**:
  2 perfiles, 2 medios, 1 solicitud fallida previa,
  **0 nuevas solicitudes, 0 resultados y 0 descargas**.
- Variables del worker verificadas sin mostrar configuración privada:
  `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=""`,
  `VIEWTV_ENABLE_DOWNLOAD_START=false`.

El worker continúa con `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
`VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=""` y
`VIEWTV_ENABLE_DOWNLOAD_START=false`. No se cambió
configuración de Jackett ni se revisaron resultados del
indexador que pudieran contener datos privados.

## Respaldo previo

Antes de editar el único archivo existente, el plan, se creó:

`/home/viewtv/viewtv-backups/jackett-capacidades-pre-20261120-204414.tar.gz`

SHA-256:
`35b64b00472ef3eb2ad0a517fe527f853d1d1d75c4ff4bbfcfeb8b44b9289795`

`tar -tzf`: contenía **solo**
`docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`.
Los dos scripts nuevos, los tests y este informe no tenían
versión anterior que respaldar.

## Qué desbloquea el siguiente paso

1. Desde VIEWTV, en «Buscar y pedir», el usuario crea una
   solicitud autorizada de una película/serie legítima.
2. Espera a que el estado sea `esperando_seleccion` o
   `sin_resultados`; si aparece un resultado, puede
   seleccionarlo sin que se añada un torrent real.
3. Si hay `sin_resultados`, comprobar en el **panel de
   Jackett** la configuración y la prueba integrada del único
   indexador. No asumir que un índice sin resultados se repara
   cambiando código de VIEWTV.
4. Con una selección confirmada, queda el ensayo autorizado
   de alta detenida, inicio con la misma ID, seguimiento y
   publicación mediante el organizador 0013.

**Estado:** seguimos teniendo que demostrar que Jackett devuelve
resultados útiles. La preparación de la descarga y la carpeta
Windows ya se habían comprobado, pero no acreditan la búsqueda
ni la descarga real.

**Despliegue:** no es necesario para este incremento; no se
modificaron aplicaciones ni contenedores, únicamente pruebas,
scripts de consulta y documentación. El PR #2 queda en borrador
sin fusionar.
