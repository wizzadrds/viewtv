# VIEWTV — corrección HLS para la segunda película (#3)

**Fecha:** 22/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Worktree autorizado:** `/home/viewtv/projects/viewtv-broker-0013-20261119`.

## Solicitud y estado

El usuario informó de que la segunda película añadida a la biblioteca no
se reproducía al pulsar «Reproducir»; también preguntó si la publicación
de nuevas películas era automática. **No lo era ni lo es todavía**:
la película #3 había sido publicada mediante `Once` supervisado,
y `VIEWTV_WINDOWS_PUBLICATION_MODE=disabled` sigue vigente
en API y worker. El Windows Service permanente no está instalado.

La película #3 está en SQLite como `completada`, `verificada`,
`organizada` y figura en Jellyfin y ViewTV, con portada.
El archivo fuente y la película publicada NO se han cambiado,
movido, recomprimido ni descargado otra vez.
«Nadie 2» es el control que el usuario ya había confirmado visualmente.

## Diagnóstico real, sin revelar medios/credenciales

- API y Jellyfin saludables. En ambos medios, Jellyfin devuelve
  `SupportsTranscoding=true` y URL privada de HLS `.m3u8`.
  La segunda película #3 es MKV HEVC 1920x1080 con AAC de 2 canales;
  «Nadie 2» MKV HEVC 3836x1600 y E-AC3/AC3.
- Jellyfin podía generar las listas y fragmentos en los dos casos;
  la variante #3 contiene **2587 fragmentos**. La versión anterior
  del proxy devolvía HTTP 200 para master, variante y segmento,
  pero el primer fragmento podía tardar mucho, por lo que eso
  no demostraba reproducción en el navegador.
- **Causa funcional identificada:** la negociación default de
  Jellyfin seleccionaba la pista ASS de subtítulos de la película
  #3, con `SubtitleStreamIndex=2` y `SubtitleMethod=Encode`.
  Logs de ffmpeg confirmaron el filtro `subtitles=...` incrustado
  durante la transcodificación H.264/AAC. Esto introducía un coste
  adicional de conversión; el comportamiento no se observó
  en «Nadie 2».
- Pasar `SubtitleStreamIndex=-1` solo en el cuerpo o query no
  surtía efecto. Una segunda negociación fijando
  **también `MediaSourceId`** devolvió HLS sin ese índice;
  master 200 en 0,33 s, variante 200 en 1,58 s y
  primer segmento `video/mp2t` 200, 65536 bytes, en 9,6 s.
  Son tiempos de una prueba, no garantía de rendimiento universal.
- Uno de los scripts iniciales de diagnóstico falló por un
  **error del propio script**: `decode('utf8-sig')` en vez de
  `decode('utf-8-sig')`. Se corrigió; aquella excepción
  **no era evidencia de fallo de Jellyfin**.

## Cambio desplegado

- `backend/app/jellyfin_playback.py`: ante una **única** fuente
  HLS no directa que trae un índice de subtítulo numérico junto
  a `SubtitleMethod=Encode`, el cliente renegocia una sola vez
  con el `MediaSourceId` validado y `SubtitleStreamIndex=-1`;
  también bloquea el resultado si Jellyfin sigue incrustando.
  Direct Play y casos de varias fuentes no se alteran.
  La PWA actual no incluye selector de subtítulos:
  se desactiva **solo** la pista incrustada automáticamente,
  sin borrar las pistas MKV originales.
- `backend/tests/test_jellyfin_playback.py`: tres regresiones
  para renegociar correctamente, fallar cerrado si persiste
  el subtítulo, y conservar varias fuentes.
- Imagen API:
  `viewtv:playback-sin-subtitulos-api-0013`
  (`sha256:bba3120c39dcaa20381f39b0bbddc49ef0f7e2e86cc5006c53259d0fdae15113`).
  Fuente en imagen y en rama con SHA-256 coincidente
  `113a136292c7a4c4d9840c8a7994c848e25b7f48bde63b0e51a1fbc10d4d4bc9`.
- `deploy/compose.playback-sin-subtitulos-0013.yaml` y
  `scripts/viewtv_compose_playback_sin_sub_0013.sh`:
  reconstrucción de overrides en orden de Compose real,
  sin imprimir secretos; `check`, `summary`, `deploy`,
  `rollback`. Se ejecutó **solo**:
  `docker compose up -d --no-deps --no-build --force-recreate api`.
  Worker 0013, Jellyfin, FlareSolverr y frontend HLS-ref-0012
  siguen sin recrear. API nueva healthy; SQLite en 0013;
  publicación Windows desactivada.

## Respaldos verificables

Antes de editar el código y los documentos existentes:

`/home/viewtv/viewtv-backups/playback-sin-subtitulos-pre-20261122-001906.tar.gz`

SHA-256:
`8385c77829e89c2738797e6984fb8030d3a1929f6d842d22b770bd4adef54dc2`.

Antes del despliegue, SQLite online consistente (origen montado
solo lectura, `sqlite3.backup`), integridad y FK OK,
versión 0013, #1/#2 excluidas y #3 organizada:

`/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-002551.db`

SHA-256:
`f17aedc1894793331be86848a27632c250e75325ae33259f412f117ab75c5766`.

Archivo con snapshot y artefactos de release:

`/home/viewtv/viewtv-backups/hls-id3-release-pre-20261122-002551.tar.gz`

SHA-256:
`a84e76fd66b201932ce594a79fefec57481276bf122bb3c537d5632adcfedc06`.

Los dos archivos `tar.gz` se comprobaron con `tar -tzf`
y `sha256sum`. La copia SQLite se verificó de manera read-only.
Scripts nuevos no tenían versión previa que respaldar.
Los diagnósticos temporales descartados quedan en el respaldo
`playback-id3-diagnostico-pre-20261122-001244.tar.gz`,
SHA-256
`3436e0719252f6a0de5b221fa5e1acaf6a3378c9b2c837cc14c36cd494f25f07`.

## Resultados posteriores a la corrección

- Suite específica de reproducción: **8/8 PASS**.
- Backend completo: **892/892 PASS**, dos avisos de deprecación
  de librerías. `ruff check --no-cache` PASS, sintaxis PASS.
  Docker de pruebas efímero y repositorio montado solo lectura,
  sin credenciales ni medios reales.
- Compose `check` PASS y `summary` confirma que worker sigue
  con auto-descarga/verificación intactos y organización `false`.
- En **API nueva real**, tanto #3 como «Nadie 2» negocian HLS;
  `SUBTITULO_INCRUSTADO_POR_DEFECTO=False` para ambos.
- Prueba privada del proxy FastAPI (auth sustituida **solo en
  el proceso efímero** de TestClient, sin modificar autenticación
  productiva): negociación 200, master 200, variante 200
  (`2.820.196 bytes`, 2587 segmentos),
  primer fragmento 200 `video/mp2t`, `873.824 bytes`.
  `API_HLS_ID3_CADENA_COMPLETA=SI`.
- Smoke read-only **10/10 PASS**, incluidos los 401 de protección
  de sesiones. SQLite y cola intactas: #3 sigue `organizada`.
  CLI de publicación `{"estado":"deshabilitado"}`.

## Verificación pendiente y reversión

**Pendiente:** reproducción visual y sonido de la segunda película
en el navegador del usuario; la entrega técnica de un fragmento
no demuestra que el reproductor haya iniciado ni que la película
completa vaya a funcionar sin interrupciones.
Pedir recarga forzada `Ctrl+F5`, «segunda película → Reproducir»,
y confirmar si aparecen imagen y sonido.

Si la nueva API no funciona, **revertir solo API**:

`bash scripts/viewtv_compose_playback_sin_sub_0013.sh rollback`

Vuelve a `viewtv:release-0013-api-candidate` con los mismos
overrides, sin mover medios ni revertir SQLite. No ejecutar
`docker compose down -v` ni restaurar un SQLite antiguo sobre #3
ya organizada.

**Automatización pendiente:** instalar y validar un publicador
Windows permanente de identidad restringida y autorización
independiente, más actualización de catálogo postescaneo sin
intervención. No declarar automática la publicación de futuras
películas ni reactivar el modo `general`.

PR #2: **OPEN/DRAFT**, sin fusionar.
