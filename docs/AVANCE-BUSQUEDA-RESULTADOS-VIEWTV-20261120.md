# VIEWTV — búsqueda GET con resultados reales; validación en PWA pendiente

Fecha: 20-11-2026. Rama exclusiva: `viewtv-seguimiento-descargas-0012`.
Plan: [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).
Registro: [issue #1](https://github.com/wizzadrds/viewtv/issues/1).

## Bloqueo del producto y conclusión

Sin resultados no es posible seleccionar ni terminar ninguna película. Los GET
anteriores para «Big Buck Bunny» y «ubuntu» habían devuelto cero resultados:
no justificaban afirmar que Jackett estuviera averiado.

El 20-11-2026 se ejecutó `scripts/viewtv_jackett_busqueda_es_readonly.py`
en el worker **existente de producción**, por stdin, sin despliegue ni
modificación de configuración. Consultó el título español conocido
**«Ocho apellidos vascos»**, únicamente mediante GET Torznab.

| Tipo Torznab | Comunicación | Elementos | Con enlace seleccionable |
| --- | --- | ---: | ---: |
| `movie` | OK | **4** | **4** |
| `search` | OK | **4** | **4** |

Ambas consultas terminaron sin errores. En una segunda ejecución se pasó
la respuesta real por `worker.processor._to_database_results` **sin guardar
SQLite**: `movie` y `search` produjeron **4 de 4 registros aptos para
guardar**. El conversor no descartó elementos por duplicados o enlaces
vacíos en esta muestra. El script nunca expone API keys, identidad del
indexador, resultados individuales, enlaces, magnets ni hashes. Los cuatro
resultados no demuestran calidad, validez ni legalidad de los ficheros,
disponibilidad de pares, selección desde VIEWTV o transferencia real.

Jackett está funcionando **para ese título y ese momento**: no se identificó
un bloqueo general por Cloudflare. No se ha modificado la URL de FlareSolverr
en Jackett ni añadido otro indexador. El servicio Windows Jackett está en
ejecución; el archivo local de log existe, pero no fue necesario examinarlo:
la instrucción de revisar log, test y dominio aplicaba si el GET daba cero.

## Evidencia adicional y límites

- Smoke de solo lectura `scripts/viewtv_release_smoke_0012_readonly.py`:
  **10/10 PASS**. Incluye HTML de PWA, proxy y API, Jellyfin y 401 sin sesión.
- El formulario real (`frontend/components/requests-panel.tsx`) usa POST
  `/solicitudes`, GET de solicitudes/resultados y POST de selección;
  esa secuencia está cubierta con proveedores ficticios en
  `backend/tests/test_release_search_selection_flow.py`. Se intentó
  reejecutar esta prueba en contenedor efímero sin red, con fuentes
  montadas en solo lectura y SQLite en memoria, pero la imagen de
  producción no incluye `pytest` (`No module named pytest`). **No se
  registra como prueba pasada en esta sesión** y no se instaló nada.
- No había una ventana abierta de VIEWTV en el navegador remoto;
  por ello no se utilizó una sesión autenticada ni se pidieron PINs.
- El único indexador previamente configurado anunciaba `movie-search`,
  `search` y `q`; esta vez respondió con resultados reales.
- **No verificado desde una sesión autenticada de «Buscar y pedir»**:
  este GET directo no crea solicitudes, no acredita que el worker guarde
  resultados en la SQLite productiva y no sustituye la prueba de la PWA.
- Las cuatro modificaciones ajenas preexistentes y los ficheros sin seguimiento
  del worktree no forman parte de este entregable.
- No se ha tocado SQLite productiva, qBittorrent, sus torrents, flags,
  Jellyfin, biblioteca, Compose, servicios ni configuración privada.
- `VIEWTV_ENABLE_TORRENT_SUBMIT=false`, `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID` vacío y `VIEWTV_ENABLE_DOWNLOAD_START=false`. Ninguna descarga activada.

## Copia previa verificada

Antes de escribir en `docs/` o crear el script se creó:

`/home/viewtv/viewtv-backups/busqueda-backlog-20261120-223037.tar.gz`

SHA-256:
`67ae19ed14ad7f2b0674f42926a60f4ce07d857f119b1aeb1d8a4aa3aa56bbe0`

`tar -tzf` confirmó el documento preexistente que íbamos a editar:
`docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`. El backlog, el script
y este informe eran archivos nuevos.

Para la ampliación del diagnóstico también se verificaron:

- `/home/viewtv/viewtv-backups/verificacion-ui-busqueda-20261120-224106.tar.gz`
  — SHA-256 `66fa942fd82bab1aa4ed5aab947cab592ffcacb0599e0002be3d606864a3e978`;
  `tar -tzf` confirmó plan, formulario PWA y prueba de integración.
- `/home/viewtv/viewtv-backups/verificacion-proveedor-conversion-20261120-224143.tar.gz`
  — SHA-256 `5f0afff4fbbb50bef041ca02cc3ccaf6ba6c157ab6d181d59e156f725ce89a60`;
  `tar -tzf` confirmó script, informe y plan previos a editar.

## Próximo paso para cerrar tarea 1

1. Desde la PWA real `http://127.0.0.1:3000`, entrar con el perfil propio.
2. En «Buscar y pedir» crear una solicitud explícita de **película** titulada
   «Ocho apellidos vascos», sin año, y esperar al resultado.
3. Confirmar `esperando_seleccion`, número de resultados y si se puede
   **seleccionar uno** sin activar el envío. Registrar la ID de descarga
   seleccionada sin publicar credenciales, magnets ni hashes.
4. Si la interfaz falla o muestra `sin_resultados`, revisar logs y test
   del indexador configurado en Jackett antes de cambiar código o buscar
   nuevos proveedores; usar FlareSolverr solo si se demuestra un bloqueo.
5. **Parar antes de dar de alta el torrent**. Obtener autorización expresa
   para la única ID, con nuevo respaldo y reversión escrita.

No se conoce ni solicita el PIN del usuario. La prueba desde la sesión real
queda pendiente; no se marca el circuito completo como verificado.

## Reversión del entregable

El código de VIEWTV en ejecución no se ha modificado, por tanto no hay
rollback de contenedores o datos. Si se desea revertir solo este avance,
retirar el script nuevo, el informe y el backlog y restaurar exclusivamente
la versión previa del plan desde el tar verificado, preservando cualquier
cambio posterior. Preferir `git revert` del commit de documentación tras
revisar su contenido; no usar `git reset --hard` ni borrar `.bak`.

## Ampliación: circuito de API sin producción (20-11-2026)

Se ha probado el mismo recorrido funcional del formulario mediante
`scripts/viewtv_search_api_sandbox.py`. Se ejecutó en un contenedor
efímero `viewtv:predeploy-0012-release`, **sin red**, con sistema de archivos
de solo lectura, código montado solo lectura, `/tmp` temporal y
`DATABASE_URL=sqlite:///:memory:`. Exige un marcador de laboratorio y
ambos permisos de torrent en `false`; no se montó la base de producción.
El proveedor Torznab es `httpx.MockTransport` con exactamente dos resultados
ficticios, sin enlaces que puedan descargarse realmente.

Salida real (exit 0): **6 comprobaciones correctas**: POST solicitud,
búsqueda y cambio a `esperando_seleccion` por cola del worker, GET de dos
resultados, aislamiento entre perfiles (404 al consultar datos ajenos),
POST selección y GET de seguimiento con una descarga `seleccionada`,
progreso cero, sin hash de qBittorrent ni intentos de envío.
Se observó una advertencia conocida de deprecación de Starlette.

**Qué desbloquea:** confirma que el backend conecta las operaciones
necesarias entre búsqueda, selección y seguimiento. Se suma al GET
real del indexador (4/4 resultados aptos); ambas evidencias son
**independientes**, no una solicitud de producción comprobada.

**Qué no está probado:** sesión real de la PWA, POST autenticado a SQLite
de producción, descarga, progreso, organización y detección en Jellyfin.
La prueba no usa PIN de usuario ni cookies. La casilla de interfaz
permanece abierta; tampoco justifica autorizar alta o inicio de torrent.

**Respaldo previo del hito**, verificado con SHA-256 y `tar -tzf`:

`/home/viewtv/viewtv-backups/ensayo-api-solicitud-pre-20261120-224647.tar.gz`

SHA-256: `30b04936bfe6810f5c5e1b6a0bd09c28a793f832fcba0c00fcc63ce7d5889737`

El tar contiene el plan, el informe de diagnóstico anterior y el test de
integración ya existente. El script nuevo no existía antes. No se
desplegaron contenedores, ni se cambiaron servicios ni variables de producción.

**Reversión:** eliminar únicamente el script de laboratorio y revertir
las líneas de esta ampliación mediante el commit, tras revisar la
reversión para conservar cambios posteriores; no restaurar SQLite ni
alterar servicios o bibliotecas. No usar `git reset --hard`.
