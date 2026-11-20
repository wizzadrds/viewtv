# VIEWTV — tamaño real de torrent y prevención de repetir selección descartada

**Fecha:** 21/11/2026. **Rama autorizada:** `viewtv-seguimiento-descargas-0012`.
**Plan maestro:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Hecho confirmado con una nueva selección real

El usuario explicó que el nombre «Nadie.2.2025.DVDRip.SPANISH»
parecía correcto, pero **el tamaño descargado en qBittorrent difería**
del anunciado por VIEWTV. El usuario seleccionó de nuevo un resultado
de ese mismo nombre en la solicitud nueva **#4**, descarga canónica
**#2**; la anterior era solicitud #3, descarga **#1**, **ya
descartada por el usuario** (en SQLite: `fallida`, solicitud
`cancelada`). La ID 2 no se ha enviado ni iniciado (0 intentos, 0 %).

Consulta de SQLite en solo lectura: ambos resultados tienen
`tamano_bytes=1503238554`, es decir, aproximadamente **1,4 GiB**.
Sus URLs y claves de resultado son distintas, pero GET read-only
restringido al Jackett configurado `/dl/` devolvió dos torrents
bencoded de metainfo. Sus diccionarios `info` son idénticos y
sus infohash SHA-1 coinciden exactamente entre sí **y con el hash
histórico de la descarga #1** en qBittorrent. Los dos anuncian el
mismo tamaño **real** `17686540911` bytes, **16,47 GiB**
(**17,69 GB**), con **dos archivos**, uno vídeo.

**Consecuencia:** la nueva ID 2 es el mismo torrent que se descartó,
aunque lo anuncia una URL distinta. No debe enviarse ni iniciarse.
La discrepancia no puede explicarse por redondeo. No se han
descargado archivos multimedia: únicamente dos respuestas
`.torrent` de metadatos en memoria, sin guardar enlaces, hashes
ni credenciales. El cotejo del título no acredita la película real
ni los derechos sobre el contenido.

## Corrección preventiva implementada

Nuevo `worker/torrent_metadata.py`:
- Permite obtener metadatos únicamente de `http(s)://<instancia
  Jackett configurada>/dl/...`, con esquema/host/puerto exactos.
  Impide redirecciones, limita las respuestas a **4 MB**, tiempo
  de espera **15 s** y analiza bencode con topes de profundidad y
  número de objetos. No descarga los medios ni envía nada a qBit.
- Extrae suma de tamaños reales de archivos y SHA-1 del **bloque
  exacto** `info` de torrent v1. Rechaza contenido malformado.
- La tolerancia por redondeo es el mayor de 20 MiB o 10 % del
  tamaño anunciado. La diferencia de 1,4 a 16,47 GiB queda
  inequívocamente fuera.
- `worker/download_processor.py` ejecuta la validación **antes
  de incrementar intentos o realizar un POST a qBittorrent**.
  Si falla la validación, guarda el fallo terminal y reabre la
  solicitud, sin registrar ni iniciar torrents. Compara además
  el infohash con descargas `fallida` de solicitudes
  `cancelada` **del mismo perfil** para no reenviar otro enlace
  que apunte a un torrent descartado.
- Conserva las protecciones anteriores: envío solo por ID
  positiva autorizada, staging fijo, `stopped=true`, sin
  arrancar torrents. Las URLs externas no se consultan como
  metadatos porque no satisfacen la lista de origen permitido.
  No altera el esquema 0012 ni la API.

## Validación y despliegue

- Tests focales **68/68 PASS**, incluyen bencode válido/malformado,
  tamaño real, hash, rechazo de dominios/puertos/redirecciones,
  límite de respuesta, bloqueo sin POST ni intento si el tamaño
  difiere, bloqueo de infohash histórico y aceptación detenida
  cuando los metadatos sí concuerdan. Se actualizó el fixture
  previo de traducción de URL de qBittorrent para simular
  correctamente el GET de metadatos.
- Backend completo **829/829 PASS** (dos avisos deprecados
  históricos, no bloqueantes).
- Nueva imagen `viewtv:validacion-tamano-0012`, derivada de
  `viewtv:qbit-async-0012`; `deploy/compose.validacion-tamano-0012.yaml`
  como capa final de Compose. `scripts/viewtv_compose_validacion_tamano_0012.sh`
  facilita preflight, actualizar y rollback del **worker
  exclusivamente**.
- Se inspeccionó Compose efectivo: envío `false`,
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID` vacía e inicio `false`.
  Se recreó **solo** el worker con `--no-deps --no-build
  --force-recreate`. API/frontend/Jellyfin sin cambios.
- Postdespliegue: worker en ejecución, API y PWA saludables;
  SQLite producción confirma ID 1 `fallida`, ID 2 `seleccionada`,
  **0 intentos de envío**, 0 %; qBittorrent solo conserva su
  torrent anterior ajeno, ninguno etiquetado como
  `viewtv-descarga-2`. **No se envió, inició, reanudó ni
  borró ningún torrent**.
- Preflight git limpio, branch autorizada; sin cambios en
  `C:\VIEWTV\media\Peliculas` ni carpetas de staging.

## Respaldos verificables

1. Código y plan antes de editar:
   `~/viewtv-backups/verificar-tamano-torrent-pre-20261121-002553.tar.gz`;
   SHA-256 `b6b15761cf81130ff647ee51c3482dbf7cdfacba60596aa6a8b8e8dc1cd9c0ce`.
2. Test previo antes de adaptar fixture:
   `~/viewtv-backups/fixture-metadata-verification-pre-20261121-002813.tar.gz`;
   SHA-256 `c94e9b8bfe08c37813e582ffd2b6631cf2072aa5218d82d759f71f6a30adb5bd`.
3. SQLite real, copia online coherente desde volumen solo lectura:
   `~/viewtv-backups/api-resultados-predeploy-20261121-003000.db.tar.gz`;
   SHA-256 `263b40cb9a30baa87ec5ceca149b2f1b36294c0d1ace5f97291d5710b972f5a8`,
   `PRAGMA integrity_check=OK`, `foreign_key_check=OK`.

Los 3 respaldos se verificaron mediante `tar -tzf`.

## Estado real y próximos pasos

**La ID 2 NO es una opción válida para el ensayo:** es el mismo
torrent anteriormente descartado y su tamaño anunciado es falso.
Solicitar al usuario usar el botón **«Deshacer selección»**
(cuando esté en estado `seleccionada`, sin envíos) y elegir un
resultado realmente distinto y autorizado. La interfaz todavía
muestra el tamaño publicado por el indexador hasta que un
candidato supera la validación.

La descarga automática completa **no está habilitada**, pues
este candidato fue descartado por identidad y tamaño. Se requieren
un resultado correcto, validación de metadatos consistente,
permiso para alta individual detenida y permiso separado para
iniciar, progresión verificada y futura publicación segura.
No hacer pruebas enviando la ID 2 al gestor.

**Rollback:** desde worktree autorizado ejecutar
`bash scripts/viewtv_compose_validacion_tamano_0012.sh rollback-worker`;
restaura `viewtv:qbit-async-0012` solo en el worker, sin
tocar SQLite. Mantener el PR #2 como draft, no fusionar.
