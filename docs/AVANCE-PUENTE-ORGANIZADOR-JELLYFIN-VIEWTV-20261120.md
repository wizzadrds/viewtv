# VIEWTV — puente de organización a Jellyfin, con publicación ficticia

**Fecha:** 20-11-2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Plan maestro:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Qué parte del producto desbloquea

La aplicación ya permite reproducir medios existentes (confirmación del
usuario) y actualizar automáticamente su catálogo, pero **no ha unido aún**
una descarga nueva y completada con la publicación segura en la biblioteca
Jellyfin. Ya existían un planificador, una cola SQLite 0013 y un copiador
**exclusivo del sandbox**. Faltaba probar el paso posterior: pedir el
escaneo de Jellyfin y comprobar que VIEWTV ve el medio tras indexarlo.

No se ha tocado la base real, ni torrents, archivos de usuario o Jellyfin.
El organizador real sigue **desactivado**, y la API/worker desplegados
siguen en versión 0012.

## Código implementado

1. `backend/app/jellyfin.py`:
   `JellyfinClient.request_library_scan()` realiza
   **POST /Library/Refresh** con la autenticación ya gestionada por
   el cliente, sin exigir JSON en una respuesta `204 No Content`.
   Los errores HTTP se convierten en `JellyfinError` sanitizado, sin
   publicar tokens, rutas o cuerpos de error. **Aceptar el POST solo
   inicia el escaneo; NO demuestra que haya concluido.**
   La operación está disponible en el código de desarrollo y
   **no está conectada** a ninguna ruta HTTP de VIEWTV ni al worker
   productivo.
2. Nuevo `worker/organization_jellyfin_bridge_sandbox.py`:
   ejecuta el runner de organización ya probado, exige
   `/tmp` con marcador explícito y que la base pertenezca a
   ese mismo sandbox. Exige una única ID de descarga elegible y
   esperada. Solicita escaneo **solo después** de que la publicación
   quede registrada `organizada` en SQLite.
   Si la publicación necesita revisión o se pierde el lease,
   **no** pide escaneo.
3. Si la solicitud de escaneo falla después de una publicación
   confirmada, devuelve `publicada_escaneo_pendiente` y permite
   una petición de escaneo independiente sobre la misma ID
   `organizada`, sin volver a copiar ni sobrescribir el vídeo.
   No existe todavía un planificador duradero de esos reintentos
   ni seguimiento del fin del escaneo en producción.
4. Nuevo `backend/tests/test_organization_jellyfin_bridge_sandbox.py`:
   pruebas con **una película ficticia** en un `tmp_path` marcado,
   SQLite aislada, copia comprobada por SHA-256 y Jellyfin simulado.
   El simulador no devuelve el título antes de completar el
   escaneo, y después `synchronize_catalog()` lo incorpora
   a `medio` con `disponible_en_jellyfin=True`.

La API de escaneo corresponde al contrato HTTP utilizado por Jellyfin:
`POST /Library/Refresh`.
Referencia de cliente existente:
https://github.com/jellyfin/jellyfin-apiclient-python/blob/master/jellyfin_apiclient_python/api.py

## Pruebas de integración

- Ejecución positiva: `completada` y `verificada` →
  organizador de sandbox publica con nombre de película →
  SQLite confirma `organizada` → solicita un escaneo una vez.
  El archivo original sigue intacto y la copia coincide por SHA-256.
- La primera consulta del catálogo **antes de finalizar el escaneo**
  devuelve cero elementos; tras finalizarlo (simulado) se incorpora
  exactamente la película ficticia.
- Protocolo Jellyfin con `httpx.MockTransport`: un único
  `POST /Library/Refresh` con cabecera de autorización, respuesta
  204 vacía admitida. Respuestas 401, 403 o 500 se traducen a un
  error sin exponer información interna.
- Fallo del escaneo: publicación conservada, no se repite la
  copia y se permite solicitar el escaneo de nuevo.
- Colisión de destino, marcador de sandbox inválido, base
  diferente, ID incorrecta, otra tarea elegible o pérdida de
  confirmación: no se solicita escaneo.
- Suite focal: **49 pruebas aprobadas**, 2 advertencias conocidas,
  incluida la regresión del planificador y del catálogo previo.
- `ruff check` y `ruff format --check`: aprobados.
- Smoke de aplicación existente: **10/10 PASS**.
- Suite completa backend: **729 pruebas aprobadas**, exit code 0
  (96,95 segundos), con 2 advertencias de deprecación conocidas
  de Starlette. Se ejecutó sin caché de pytest ni bytecode.

La primera ejecución de la prueba integrada detectó una ruta
incompleta **en el simulador de Jellyfin** (omitía `Peliculas`).
Se corrigió la ruta ficticia y las 49 pruebas focales pasaron.
No implicó un fallo ni cambio sobre medios productivos.

## Respaldo antes de modificar archivos existentes

`/home/viewtv/viewtv-backups/jellyfin-puente-post-publicacion-pre-20261120-205256.tar.gz`

SHA-256:
`7cd4f61ca5407957be624ce049cc4a7ac4981a1ed977c6f17adac7bd6f67e6c2`

Se comprobó con `tar -tzf` que incluye **solo**:
- `backend/app/jellyfin.py`
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`

El módulo de puente, las pruebas y este informe son nuevos; no
tenían archivos anteriores que respaldar.

## Despliegue y recuperación

**Este avance NO se ha desplegado**: ningún nuevo contenedor, variable,
migración Alembic, cambio de volumen o llamada POST a Jellyfin real.
Se conserva la instalación funcional con API 0012,
worker `viewtv:inicio-torrent-unico-0012` y frontend actual.
Los permisos de inicio y alta de torrents siguen desactivados.

**Recuperación:** al ser una modificación solo del árbol Git,
se puede abandonar el puente sin alterar nada en producción.
El sandbox no sobrescribe destinos existentes; si existe una
publicación ambigua tras interrupción, su estado requiere revisión.
El código de recuperación de laboratorio no se usará sobre vídeos reales.

## Qué falta para que esta función sea REAL

1. Un único ensayo de búsqueda/selección con resultado real del
   proveedor, autorizado por la persona usuaria.
2. Una transferencia identificada y autorizada, con carpeta
   Windows comprobada y permisos de inicio controlados por ID.
3. Un ejecutor de publicación Windows independiente, confinado
   y durable para `0013`, sin accesos de escritura generales
   del worker y con manejo explícito de caídas/colisiones. El
   copiador Linux `/tmp` **no es desplegable directamente** en
   las bibliotecas de NTFS.
4. Revalidar identidad de torrent y lease en la autoridad que
   realmente publica; verificar el archivo destinado y recuperar
   ambiguos sin borrado ni copia ciega.
5. Con el archivo de demostración publicado y permisos autorizados,
   probar el escaneo **real** de Jellyfin, esperar a que termine,
   comprobar que la sincronización automática lo incorpora a
   VIEWTV y reproducirlo.
6. Ensayar migración y reversión de 0012 a 0013 sobre una
   copia actual de SQLite antes de una autorización de despliegue.

**Resultado exacto:** el circuito sintético hasta catálogo
funciona, pero la publicación en Windows y la detección real
por Jellyfin siguen pendientes. No presentar este avance
como integración productiva completa.
