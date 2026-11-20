# VIEWTV 0013 — sonda HTTP GET de identidad de torrent (solo sandbox)

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.

**SOLO ENSAYO; NO CONSULTO qBittorrent REAL NI AUTORIZO PUBLICACIONES.**

## Objetivo

Ya existía `worker/organization_torrent_guard.py`, capaz de verificar
identidad y archivos mediante un cliente qBittorrent simulado.
Esta iteración añade una frontera HTTP verificable con controles
sobre el transporte, el formato de respuestas, la etiqueta
de propiedad y la integridad declarada de los archivos.

Código nuevo: `worker/organization_qbit_http_probe_sandbox.py`.
Pruebas nuevas:
`backend/tests/test_organization_qbit_http_probe_sandbox.py`.

La función `check_sandbox_torrent_http()` devuelve solo
`TorrentProbeDecision(allowed, code)`. La decisión positiva
corresponde **únicamente al instante de consulta** y no sustituye
la revisión de bytes NTFS ni el permiso para mover archivos.

## Frontera del HTTP ficticio

- URL exacta `http://127.0.0.1:<puerto-alto>`, con puerto entre
  49152 y 65535; sin nombres DNS, credenciales, path, query ni HTTPS.
  No utiliza configuración de producción ni sigue redirecciones.
- Credencial ficticia literal `VIEWTV_SANDBOX_TEST_ONLY`,
  **nunca una clave de VIEWTV o de qBittorrent real**.
- Antes de consultar torrents, GET
  `/viewtv-test/marker?guid=<GUID>`; exige un JSON exacto de tres
  campos, versiones y tipos validados, `test_only=true` y el GUID
  de sandbox indicado. El marcador sirve para detectar una fuente de
  ensayo; **no constituye autenticación criptográfica**.
- Solo después ejecuta GET
  `/api/v2/torrents/info?hashes=<hash>` y, cuando la
  identidad está bien formada, GET
  `/api/v2/torrents/files?hash=<hash>`.
- Cada respuesta tiene límite de 16 KiB; JSON con claves repetidas,
  constantes no finitas, redirects, errores HTTP, timeouts y
  respuestas truncadas se rechazan.
- Se exige **un solo** hash coincidente, `viewtv-descarga-<id>`
  en la etiqueta, ausencia de etiquetas VIEWTV contradictorias,
  un estado de descarga terminada reconocido y progreso exactamente 1.
- El directorio declarado debe ser el de staging **ficticio**
  `C:\Users\Public\viewtv-win-sandbox-<GUID>\stage`,
  no `C:\VIEWTV\media`.
- La lista declarada contiene entre 1 y 20 archivos, tamaño total
  máximo 32 MiB, exactamente un vídeo y, opcionalmente, subtítulos.
  Rechaza rutas absolutas, escapes, nombres reservados Windows,
  colisiones de mayúsculas/minúsculas, extensiones inesperadas,
  archivos sin prioridad o incompletos y tamaños incoherentes.
  **No se abre ninguno de esos archivos:** solo se inspeccionan
  metadatos ficticios devueltos por HTTP.

## Resultados

La batería específica terminó **70 passed**, exit code 0, con
`ruff check` aprobado. La suite backend completa en Ubuntu terminó
**615 passed, 2 warnings** conocidos, exit code 0 (40,20 segundos),
sin caché ni bytecode generados deliberadamente. Incluye simulaciones HTTP de:
etiqueta ajena, hash distinto, duplicados, progreso parcial,
directorio extraño, tamaño alterado, más de un vídeo, nombre
con escape, prioridad 0, redirección 3xx, errores 4xx/5xx,
JSON ambiguo, respuesta excesiva y caída de conexión.

**Una prueba adicional estableció un servidor HTTP real de ensayo**
solo en `127.0.0.1`, puerto alto libre, con datos ficticios,
y demostró tres peticiones GET y **cero POST**; el servidor se
apagó, cerró su socket y terminó el hilo dentro del test.
Los demás casos usan `httpx.MockTransport` y jamás alcanzan
el cliente de torrents real.

No se utilizaron rutas de medios reales ni credenciales, y no
se instalaron servicios o cuentas de sistema.

## Límites estrictos y próximos pasos

1. **Actualización posterior:** la sonda se conectó en la modalidad
   de servidor v3 del canal de admisión sandbox, junto al lease de
   SQLite ficticia. El servidor fija la URL de ensayo; el cliente
   no puede indicar el origen. Véase
   [ORGANIZADOR-DOBLE-GATE-LEASE-TORRENT-PIPE-SANDBOX.md](ORGANIZADOR-DOBLE-GATE-LEASE-TORRENT-PIPE-SANDBOX.md).
   Aún falta una autoridad independiente real y la revisión final
   antes de mover archivos; NO es una ruta de producción.
2. El marcador no autentica una fuente hostil y la credencial
   de ensayo es pública; este test no debe usarse en producción.
3. No se ha consultado un qBittorrent real. Tampoco se ha cotejado
   el torrent con la SQLite real, el lease vigente, ACL Windows o
   manifest de publicación. El estado HTTP cambia con el tiempo.
4. Deben existir SIDs realmente separados, broker de servicio sin
   privilegios de administración, secreto independiente,
   comprobación final antes de mover y recuperación durable.
5. Las pruebas de tamaño máximo 32 MiB no equivalen a ensayos
   con ficheros reales de varios GiB.
6. Despliegue 0013 y merge del PR #2 siguen prohibidos hasta
   completar todas las fases y contar con autorización.

**Respaldo:** ambos archivos de código y prueba de esta iteración
son **nuevos** en la rama; no había versiones preexistentes que
respaldar. Antes de trabajar se verificó Git limpio y sincronizado.
No se ha modificado ningún archivo, SQLite o biblioteca existente.
