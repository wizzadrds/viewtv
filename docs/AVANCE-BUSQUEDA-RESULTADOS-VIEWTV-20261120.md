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

Ambas consultas terminaron sin errores. El script nunca expone API keys,
identidad del indexador, resultados individuales, enlaces, magnets ni hashes.
Los cuatro resultados no demuestran calidad, validez ni legalidad de los
ficheros, disponibilidad de pares, selección desde VIEWTV o transferencia real.

Jackett está funcionando **para ese título y ese momento**: no se identificó
un bloqueo general por Cloudflare. No se ha modificado la URL de FlareSolverr
en Jackett ni añadido otro indexador. El servicio Windows Jackett está en
ejecución; el archivo local de log existe, pero no fue necesario examinarlo:
la instrucción de revisar log, test y dominio aplicaba si el GET daba cero.

## Evidencia adicional y límites

- Smoke de solo lectura `scripts/viewtv_release_smoke_0012_readonly.py`:
  **10/10 PASS**. Incluye HTML de PWA, proxy y API, Jellyfin y 401 sin sesión.
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
