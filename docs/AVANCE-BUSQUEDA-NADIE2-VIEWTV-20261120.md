# VIEWTV — diagnóstico de «Nadie 2» y búsqueda real de la PWA

Fecha: 20-11-2026. Rama exclusiva: `viewtv-seguimiento-descargas-0012`.
Plan: [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Bloqueo funcional observado

El usuario ha confirmado desde «Buscar y pedir» dos solicitudes:
- «Nadie 2», tipo película, sin año: `sin_resultados`.
- «Nadie 2» con año 2025, creada anteriormente: `fallida`.

El log real del worker registra para la solicitud **2**:
`Solicitud 2 procesada: 0 resultados seleccionables`.
Por tanto, el recorrido de creación y procesamiento sí funcionó;
la petición sin año no devolvió resultados para guardar. La solicitud
fallida antigua había agotado reintentos por comunicación con Jackett:
no se ha reabierto, reintentado ni alterado.

## GET reales, sin escribir solicitudes

Se creó `scripts/viewtv_jackett_nadie2_readonly.py` y se ejecutó
por stdin dentro del worker 0012 existente. Solo consulta Torznab GET
con su configuración vigente. No publica API key, URL, nombre de
indexador, enlaces, torrents, títulos retornados o hashes.

| Término | Tipo | Resultados | Aptos para guardar |
| --- | --- | ---: | ---: |
| Nadie 2 | movie | 0 | 0 |
| Nadie 2 2025 | movie | **62** | **62** |
| Nobody 2 | movie | 0 | 0 |
| Nobody 2 2025 | movie | 0 | 0 |
| Nobody 2 | search | 0 | 0 |

El título original de «Nadie 2» (2025) es «Nobody 2» según
el Catálogo ICAA del Ministerio de Cultura, pero esa traducción
**no reparó la búsqueda** en este indexador.

Segundo GET con «Nadie 2 2025»: de los 62 registros aptos,
solo **3** incluyen en su título el término «nadie» o «nobody»
y el número separado «2»; solo **2** mencionan 2025.
Son coincidencias textuales, **no** verificación del contenido,
edición, derechos, integridad, presencia de pares o descarga.
La mayoría de los 62 elementos son coincidencias amplias y no
deben tratarse como una lista fiable de la película.

## Diagnóstico de proveedor, sin cambiar configuración

- El servicio Windows Jackett seguía `Running`; se observó
  **1 indexador configurado**, capacidades GET `caps` correctas
  para `search`, `movie-search`, `tv-search` y `q`.
- El GET administrativo existente devolvió `NO_VERIFICABLE`:
  no permite confirmar el resultado de la prueba interna de la
  interfaz de Jackett. Esta prueba del panel **no se ejecutó**.
- En las últimas 500 líneas del log local, diagnóstico agregado
  sin mostrar contenido: 42 coincidencias con TLS/SSL/certificate,
  una con HTTP 403 y cero referencias a Cloudflare. No se ha
  demostrado que estos errores correspondan al indexador activo
  ni que Cloudflare bloquee esta consulta.
- Se mantuvieron intactos dominio, FlareSolverr y la lista de
  indexadores: la consulta con año tuvo respuesta y cambiar la
  configuración ahora no tiene justificación demostrada.

## Qué se ha desbloqueado y qué falta

**Confirmado:** la interfaz creó la solicitud y el worker la procesó;
el GET con año puede producir candidatos visibles, pero con muchos
falsos positivos. No se ha probado aún que esa variante genere
`esperando_seleccion` desde la PWA real ni que se pueda seleccionar
un elemento adecuado.

**Siguiente prueba mínima en la UI:** crear **una solicitud nueva**
de película «Nadie 2» con año **2025**. La anterior con año está
`fallida` y no se reintentará por sí sola. Esperar el refresco
automático; comprobar que llega a `Resultados disponibles` y
revisar cuidadosamente el título y año de los candidatos. No
seleccionar contenidos sin derecho a obtenerlos. Si aparece un
resultado autorizado, registrar el ID de descarga tras seleccionarlo
con las banderas de envío e inicio desactivadas.

Si vuelve a fallar o a devolver cero, pasar a la prueba del indexador
desde la UI de Jackett y sus logs específicos; solo corregir
dominio/Cloudflare/FlareSolverr cuando haya evidencia del fallo.

No se han creado solicitudes, torrents o descargas desde el conector;
no se ha tocado la SQLite de producción, `C:\VIEWTV\media`,
bibliotecas, Compose ni servicios. El worker mantiene la política
de alta/inicio desactivados y la ID de ensayo vacía. Servicio sano
no equivale a transferencia verificada.

## Respaldos previos, verificados

1. `/home/viewtv/viewtv-backups/nadie2-diagnostico-pre-20261120-225219.tar.gz`
   SHA-256 `592e319700767429185a97fc2d8c96b4234be0996ed74d42df3f107c18a88eff`.
   `tar -tzf`: plan, informe anterior y script de búsqueda.
2. `/home/viewtv/viewtv-backups/nadie2-relevancia-pre-20261120-225339.tar.gz`
   SHA-256 `8eb2f657c8ac0e96c6238c1265b3e650e3f018998fec5eb4e515e8cdfbeb193f`.
   `tar -tzf`: plan, informe anterior y nuevo script de Nadie 2,
   antes de ampliar la clasificación por títulos.

## Reversión y alcance

El cambio no requiere despliegue: solo script de diagnóstico,
documentación y casillas del plan. Para revertirlo, revisar
`git revert` del commit del hito y conservar cambios posteriores;
no tocar SQLite ni servicios. No usar `git reset --hard` ni borrar
archivos `.bak`.

**Pendientes no verificados:** elección real de un resultado
apropiado en la PWA; alta detenida con autorización e ID; inicio
con autorización separada; transferencia, progreso, verificación,
organización y aparición en Jellyfin.
