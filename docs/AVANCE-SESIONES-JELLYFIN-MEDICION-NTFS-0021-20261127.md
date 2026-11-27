# VIEWTV 0021 — Barrera Jellyfin por sesiones y medición de espacio NTFS

**Fecha:** viernes 27 de noviembre de 2026, Europe/Madrid.
**Repositorio:** `wizzadrds/viewtv`.
**Rama:** `viewtv-seguimiento-descargas-0012`; **PR #2 OPEN/DRAFT, sin fusionar**.
**Prioridad:** completar gestión de espacio y retirada segura ANTES de la aplicación Samsung Tizen. «VIEWTV Momentos» queda después.

## Qué se ha hecho

Este hito incorpora **una nueva barrera de reproducciones Jellyfin basada en lecturas GET** y un **ensayo real sobre Windows NTFS** para medir el cambio de espacio libre antes y después de retirar hardlinks propios de un archivo *exclusivamente ficticio*.

**Cero películas reales eliminadas. Cero torrents pausados, borrados o modificados. No se actualizó ningún contenedor, esquema SQLite ni configuración de producción.** La funcionalidad destructiva continúa deliberadamente deshabilitada.

### A. Barrera de reproducción en Jellyfin (solo lectura)

Nuevos archivos:

- `worker/retirement_playback_guard_0021.py`: evaluador puro de la respuesta a Jellyfin `GET /Sessions`, con límites máximos, IDs de sesión únicos y validación estricta de los ID Jellyfin del catálogo.
- `scripts/viewtv_retirada_jellyfin_sesiones_0021.py`: realiza **dos GET** de sesiones, los compara por una instantánea normalizada y evalúa las cuatro películas registradas, sin nombres de perfil, dispositivo, archivos, rutas ni hash en la salida.
- `scripts/viewtv_retirada_jellyfin_probe_run_0021.py`: ejecuta la prueba **en memoria dentro de la API existente** mediante `docker exec -i ... python -`. Carga el módulo del worktree en `sys.modules` de un proceso Python efímero; no lo copia al contenedor ni modifica imágenes, API, claves, credenciales, bases de datos o archivos. Aplica lista blanca a cada campo de stdout y oculta stderr.
- `backend/tests/test_retirada_reproduccion_0021.py`: matriz de sesiones e identidades ficticias.
- `backend/tests/test_retirada_jellyfin_runner_0021.py`: comprueba aislamiento de stdout, errores, timeouts, firma de comandos read-only y que no se permitan indicaciones de borrado.

Política conservadora:

- La película en reproducción se **bloquea**, aunque la sesión esté pausada.
- Si `NowPlayingItem` no tiene ID seguro o hay transcodificación sin ítem identificable, la sesión es **ambigua** y se bloquean las películas que se intenten evaluar.
- Sesiones duplicadas, inventario inválido, demasiadas sesiones, IDs imposibles, errores HTTP o cambios entre lecturas no son un permiso; **fallan cerrados**.
- Una película distinta que se reproduce en otra sesión no bloquea por sí sola al ítem consultado, siempre que los ID sean únicos y válidos.
- **Incluso con cero sesiones reportadas** el resultado incluye `habilita_borrado_fisico=false` y `SIN_BLOQUEO_TRANSACCIONAL=SI`.

Salida de producción obtenida solo mediante dos consultas GET autorizadas:

```text
JELLYFIN_SESIONES_0021=SOLO_GET
ESTADO=sin_reproduccion_reportada
PELICULAS_COMPROBADAS=4
PELICULAS_BLOQUEADAS=0
SESIONES_JELLYFIN=0
SESIONES_PELICULA_OBJETIVO=0
SESIONES_OTRAS_PELICULAS=0
SESIONES_AMBIGUAS=0
SIN_BLOQUEO_TRANSACCIONAL=SI
AUTORIZA_BORRADO_FISICO=NO
REPRODUCCIONES_MODIFICADAS=0
ARCHIVOS_ELIMINADOS=0
```

**Limitación esencial:** `/Sessions` no impide que una sesión empiece justo después, ni garantiza detectar todas las transmisiones directas/HTTP si el reproductor no informa actividad a Jellyfin. **No se ha habilitado ninguna retirada por esta lectura**. El ejecutor final requerirá exclusión de nuevos inicios, revisión de descriptores/archivos abiertos en Windows, auditoría de accesos en Jellyfin y revalidación en el momento del unlink; al menor desacuerdo, deberá bloquear.

### B. Medición real del volumen NTFS exclusivamente en sandbox

Archivo nuevo `scripts/viewtv_windows_espacio_fisico_sandbox_0021.ps1`.

- No admite rutas, ID de película, hash de torrent ni modos de producción.
- Crea una carpeta temporal `viewtv-0021-ficticio-{GUID}` en TEMP local del usuario, con un marcador de propiedad de la propia prueba. Nunca escribe en la biblioteca `C:\VIEWTV\media`.
- Compara la raíz de volumen de TEMP con la raíz de volumen de la carpeta media mediante `GetVolumePathNameW` (Win32). El resultado fue **TRUE** para este ensayo.
- Escribe y fuerza a disco un archivo **sintético de 8 MiB**, con contenido aleatorio no procedente de películas; crea otro hardlink en la misma carpeta.
- Verifica mediante Windows `GetFileInformationByHandle` que las referencias pertenecen al mismo archivo NTFS y tienen contador de enlaces **exactamente dos**.
- Mide el espacio libre con **`GetDiskFreeSpaceExW`** antes de escribir, después de escribir, después de crear el enlace, después de retirar el primer enlace y después de retirar el último.
- No elimina ningún otro archivo: borra sus enlaces ficticios, su propio marcador y su carpeta GUID al finalizar. Se rechaza cualquier reparse path o entrada ajena en el sandbox.

Resultado observado:

```text
MEDICION_DISCO_GETDISKFREESPACEEXW=PASS
VOLUMEN_SANDBOX_COINCIDE_CON_MEDIA=TRUE
TAMANO_LOGICO_ENSAYO_BYTES=8388608
DELTA_LIBRE_AL_CREAR_BYTES=-8388608
DELTA_LIBRE_AL_CREAR_HARDLINK_BYTES=-4096
DELTA_LIBRE_AL_QUITAR_PRIMER_LINK_BYTES=0
DELTA_LIBRE_AL_QUITAR_ULTIMO_LINK_BYTES=8388608
DELTA_NO_ATRIBUIBLE_CON_CERTEZA=SI
DOS_ENLACES_FICTICIOS_BORRADOS=PASS
ARCHIVOS_REALES_BORRADOS=0
TORRENTS_REALES_MODIFICADOS=0
```

La diferencia al crear un hardlink corresponde a metadatos del sistema de ficheros observados en la prueba. Los **8 MiB recuperados tras el último unlink** son una *observación del volumen* coherente con la liberación de los bloques del archivo sintético. No se puede atribuir la cifra exacta al archivo si otros procesos modifican simultáneamente el disco, si existe compresión, deduplicación, snapshots o reservas; en producción, se deberá registrar el delta antes/después y explicar estas limitaciones. No hay ninguna garantía de poder recuperar el tamaño lógico completo de una película real.

### C. Pruebas, reversión y seguridad

- **47/47 pruebas específicas** de sesiones, bloqueo, privacidad y runner en laboratorio sin red.
- **Ruff PASS** en los cinco archivos Python nuevos.
- **Suite backend completa: 1206/1206 PASS**, con 2 advertencias de deprecación de dependencias externas, ejecutada en contenedor de pruebas sin acceso a la red.
- **Smoke real de solo lectura 10/10 PASS**; API y frontend saludables, Jellyfin saludable. **Preflight 0018 real** 4/4 películas bloqueadas, 2 torrents activos, 2 diarios NTFS verificados, 0 borrados. Auditoría posterior de Windows: 2/2 diarios válidos, 0 bloqueados, 1 carpeta sin diario protegida, 0 eliminaciones reales.
- Copia previa validada de documentación existente:
  `/home/viewtv/viewtv-backups/retiro-sesiones-ntfs-pre-20261127-161546.tar.gz`
  SHA-256 `00ce76f4bc7518040613970b0d98d631e4dddb53514eb35c81b057bd9d9c4915`.
  `tar -tzf` correcto; no incluye películas, `.env`, contraseñas ni bases de datos.
- **Ninguna migración de SQLite, reinicio, build o despliegue en producción**; no hay nada que revertir en contenedores. Se puede revertir únicamente el commit Git sin alterar servicios. Se conserva la configuración y los respaldos del hito 0017.

### D. Qué falta para eliminar una película física y seguramente

1. Identidad real y custodia del secreto administrativo en Windows/WSL, con mecanismo de aprobación por una película concreta, revocación y consumo único. El hito 0019 sigue **solo en pruebas**.
2. **Bloqueo integrado de reproducción y aperturas** para evitar que Jellyfin inicie un stream mientras el ejecutor hace su trabajo. `GET /Sessions` es una prueba auxiliar, no una exclusión atómica.
3. **Bloqueo común con publicador Windows y qBittorrent**, relectura del estado justo antes de actuar y prohibición de parar torrents sin permiso específico. Los dos torrents estaban activos en las últimas comprobaciones 0020.
4. Mantener protegidos los **cuatro metadatos extras** del inventario qBit 0020 (488 bytes lógicos) y la carpeta sin diario. La titularidad, las rutas y los enlaces compartidos deben estar probados; no basta que sean archivos pequeños.
5. Asociar el diario NTFS durable de ensayo 0020 con autorización firmada, reserva exclusiva de origen/publicación, cancelación, recuperación tras apagón y prueba de fallos parciales. El laboratorio no es todavía un ejecutor de producción.
6. Medir los bytes libres reales antes/después de cada operación y registrar los resultados sin inventar equivalencia con los tamaños lógicos. **Ningún borrado real sin autorización concreta y controles completos.**

**Orden preservado: espacio y retirada segura → app Samsung instalable profesional → VIEWTV Momentos.**
