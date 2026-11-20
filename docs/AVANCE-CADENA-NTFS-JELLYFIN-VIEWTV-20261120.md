# VIEWTV — cadena Docker, NTFS Windows y catálogo Jellyfin simulado

**Fecha:** 20 de noviembre de 2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Prioridad:** cerrar la cadena de publicación con una prueba real en NTFS,
sin desplegar el organizador ni acceder a archivos multimedia del usuario.
**Plan:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Hallazgo y solución

El organizador 0013 ya tenía **dos ensayos parciales**, pero no unidos:

- El ensayo Windows existente preparaba y copiaba un vídeo ficticio y un
  subtítulo desde Docker; Windows publicaba la carpeta usando su API
  nativa `Directory.Move` y verificaba la publicación mediante plan
  HMAC de laboratorio y reconciliador de lectura.
- El puente de laboratorio posterior simulaba `POST /Library/Refresh`
  y después incorporaba una película al catálogo `medio`, pero solo
  con publicación bajo `/tmp` Linux.

**En esta entrega se conectaron esos tramos en una sola ejecución sobre
el NTFS real del equipo Windows**, siempre en un directorio
`C:\Users\Public\viewtv-win-sandbox-<GUID>` recién creado con marcador
explícito. La solicitud a Jellyfin sigue usando exclusivamente
`httpx.MockTransport` y la base de datos es SQLite **en memoria**.

## Código añadido y corregido

- `worker/organization_cross_runtime_probe.py`: el ensayo de Docker
  ahora monta en solo lectura el **árbol de desarrollo autorizado**
  `/home/viewtv/projects/viewtv-broker-0013-20261119`, no la copia
  original de referencia, que se mantiene sin modificaciones.
- `scripts/test_cross_runtime_windows_publish.ps1`: después de
  verificar el staging de Docker, llama al nuevo comprobador de
  catálogo en fase `before` y exige **cero solicitudes de escaneo**.
  Tras publicación nativa Windows y reconciliación
  `publicada_verificada` del manifiesto firmado, lo llama en fase
  `after` y comprueba que solo entonces se realiza un POST de escaneo
  ficticio y que la película aparece en el catálogo simulado después
  de terminar su indexación.
  El script sigue firmando el plan con una clave temporal aislada,
  verificando SHA-256 de vídeo y subtítulo, rechazando la adulteración
  del staging y la sobrescritura, comprobando el origen intacto y
  limpiando **solo su directorio nuevo marcado y su clave efímera**.
- Nuevo `worker/organization_windows_catalog_probe_sandbox.py`:
  reutiliza el validador de ruta exclusiva de sandbox Windows.
  Antes de publicar rechaza todo destino existente y devuelve
  cero escaneos. Después exige ausencia del staging y presencia
  exacta de vídeo y subtítulo regulares, sin enlaces ni archivos
  adicionales. Utiliza `JellyfinClient.request_library_scan()` real
  del código Python, pero con transporte **HTTP simulado** y
  credencial ficticia; tres consultas sintéticas de catálogo
  validan 0 antes, 0 después del POST y 1 una vez declarado
  terminado el escaneo simulado. Una SQLite `sqlite://` en memoria
  registra `Medio` únicamente en ese último paso.
  No acepta rutas arbitrarias fuera del sandbox marcado en su CLI.
- Nuevo `backend/tests/test_organization_windows_catalog_probe_sandbox.py`:
  **13 pruebas** con `tmp_path` ficticio: fases, publicación positiva,
  carpeta ausente, staging ambiguo, vídeo/subtítulo incompletos,
  archivo adicional, symlink, parámetro inválido y rechazo de rutas
  ajenas por el validador real.

**Importante:** el comprobador no autoriza movimientos por sí solo ni
admite manifestaciones de aprobación aportadas libremente. La prueba
PowerShell primero invoca el publicador y reconciliador firmados y
después el comprobador, que solo tiene acceso al sandbox. No puede
escanear Jellyfin real: el transporte HTTP está fijado a
`httpx.MockTransport` y el host `jellyfin-ficticio.invalid`.

## Ejecución en el equipo

Se ejecutó desde PowerShell nativo Windows el harness versionado del
árbol de desarrollo (sin escribir en otras rutas), con vídeo binario
ficticio de unos **3 MiB** y un subtítulo de texto sin contenido real.
Docker recibió solo la carpeta ficticia de prueba, sin red, con
capabilities retiradas, `--read-only`, `--user 1000:1000` y
código fuente montado en lectura.

**Resultados reales, 8/8 correctos:**

```json
{
  "docker_staging_y_sha256": "correcto",
  "prepublicacion_sin_escaneo": "correcto",
  "tamper_docker_rechazado": "correcto",
  "publicacion_multifichero_ntfs": "correcto",
  "reconciliacion_de_lectura": "publicada_verificada",
  "ntfs_jellyfin_catalogo_ficticio": "correcto",
  "segundo_intento_sin_sobrescritura": "correcto",
  "origen_intacto": "correcto"
}
```

La publicación Windows fue **real solo dentro del sandbox temporal**.
La película en el catálogo fue **ficticia**; no se indexó un vídeo real,
no se hizo POST a Jellyfin productivo y no se escribió SQLite productiva.
El harness conserva su limpieza estricta por nombre GUID y marcador
y salió con exit code 0.

## Tests y verificaciones

- Python focal del puente de Windows: **13/13 aprobados**.
- Integración PowerShell sobre NTFS Windows: **8/8 controles correctos**.
- Análisis PowerShell AST: **válido**.
- Ruff `check` y `format --check` de los nuevos Python: correctos.
- Smoke VIEWTV de solo lectura: **10/10 correcto**.
- Suite completa backend: **742 pruebas aprobadas**, exit 0
  (95,67 segundos), con 2 avisos de deprecación conocidos
  de Starlette y sin caché de pytest ni generación de bytecode.
- No se han recreado contenedores productivos, migrado SQLite,
  habilitado envío/inicio de torrents, abierto ficheros de medios reales,
  cambiado ACL de bibliotecas ni ejecutado escaneo Jellyfin real.

## Respaldo selectivo previo

`/home/viewtv/viewtv-backups/cadena-ntfs-jellyfin-pre-20261120-210535.tar.gz`

SHA-256:
`413a5f669039e61c43ecda91f2828330b3bca612da62d2e07c9a2985dcea4f98`

`tar -tzf` verificó **exactamente**:
- `worker/organization_cross_runtime_probe.py`
- `scripts/test_cross_runtime_windows_publish.ps1`
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`

Los dos archivos de Python del nuevo puente y sus pruebas, además de
este informe, son nuevos y no requerían copia anterior.

## Lo que todavía falta para poder entregar el organizador

1. Hay **prueba real de publicación en NTFS**, pero no un servicio
   ejecutor estable y confinado en producción. El entorno Windows
   de sandbox de Public no equivale a los permisos/ACL de las
   bibliotecas de Jellyfin. La autoridad que valida lease y torrent
   al publicar no está integrada productivamente con 0013.
2. Hay **prueba simulada de escaneo y catálogo**, pero no se ha
   probado que Jellyfin real detecte un fichero publicado por
   el organizador en una biblioteca de demostración.
3. Falta un ensayo autorizado de descarga legítima para validar
   Jackett, qBittorrent, progreso, verificación y publicación.
   Jackett respondió a búsquedas de ejemplo pero devolvió
   cero resultados; el indexador configurado soporta los tipos
   de búsqueda y aún no se ha acreditado el caso real positivo.
4. Antes de desplegar 0013: backup actual, prueba de
   migración/reversión, identidad independiente de la autoridad,
   recuperación de cortes NTFS y permisos mínimos, y prueba
   completa usando solo medios de demostración autorizados.

Se mantiene `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
`VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID=""` y
`VIEWTV_ENABLE_DOWNLOAD_START=false` en la instalación operativa.
El PR #2 sigue **abierto en borrador**, no fusionado.
