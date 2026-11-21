# VIEWTV — resultados aparentemente distintos que son el mismo torrent

**Fecha:** 21 de noviembre de 2026. **Rama:** `viewtv-seguimiento-descargas-0012`.

## Diagnóstico con metainfo real de Jackett (solo lectura)

El usuario informó de que `Nadie.2.2025.4K.4K.SPANISH`
mostraba «Torrent descartado anteriormente» y parecía que el
bloqueo se extendía a todos los resultados.

Se examinaron por GET **solo metadatos** de los siete resultados
actuales de las solicitudes #4 y #6; los hashes no se registraron
en el informe ni se expusieron al usuario.

| Solicitud | Resultado | Tamaño real | Coincide con descarga #1 descartada |
|---|---|---:|---|
| #4 (Nadie 2) | Nadie.2.2025.4K.4K.SPANISH | 16,47 GiB | **Sí** |
| #4 (Nadie 2) | Nadie.2.2025.DVDRip.SPANISH | 16,47 GiB | **Sí** |
| #6 (La Odisea) | La.Odisea.2026.4K.4K.SPANISH | 30,98 GiB | No |
| #6 (La Odisea) | La.Odisea.2026.BluRay.1080p.SPANISH | 6,33 GiB | No |
| #6 (La Odisea) | La.odisea.de.los.Giles.2019.HDRip.SPANISH | 1,01 GiB | No |
| #6 (La Odisea) | La.Odisea.2026.DVDRip.SPANISH | 4,59 GiB | No |
| #6 (La Odisea) | La.odisea.2026.DVDRip.SPANISH | 4,30 GiB | No |

Los dos resultados de «Nadie 2» tienen **exactamente el
mismo infohash del .torrent**, idéntico al que el usuario
retiró manualmente como incorrecto; las diferencias de
nombre, resolución y tamaño anunciadas por Jackett
**no hacen que sean alternativas diferentes**.

Por contraste, las cinco opciones para «La Odisea»
son cinco hashes distintos y no fueron descartadas.
Eso no acredita por sí mismo que sus vídeos coincidan
con el título buscado.

## Corrección de interfaz

Solo `frontend/components/requests-panel.tsx`:

- Un resultado bloqueado por histórico muestra
  **«Ya descartado»** en lugar de un botón que parecía
  ofrecer «Descargar», siempre deshabilitado.
- El mensaje explica que es el **mismo archivo .torrent**
  descartado aunque el título del resultado difiera.
- Cuando todas las opciones visibles están bloqueadas
  por histórico, se presenta un resumen:
  «No hay opciones nuevas entre estos resultados».
- Las opciones aptas mantienen el botón **«Descargar»**;
  mientras se verifican aparece «Consultando…»,
  y si no se puede leer el metainfo «No disponible».
- Se conserva el **único tamaño real** del .torrent,
  la consulta automática de metadatos y el
  opt-in de transferencias automáticas para ID futuras.

No se modifica ningún estado de SQLite, la API, worker,
qBittorrent, discos ni Jellyfin. No se desbloquea
ni se vuelve a enviar la descarga descartada #1.

## Validación y despliegue

- Compilación Next.js/TypeScript en imagen
  `viewtv-frontend:descartados-claros-0012`.
- `deploy/compose.descartados-claros-0012.yaml`
  y `scripts/viewtv_compose_descartados_claros_0012.sh`
  permiten desplegar y revertir **solo la PWA**,
  respetando el umbral de seguridad persistido de
  la cola automática `VIEWTV_AUTO_DOWNLOAD_AFTER_ID=1`.
- Verificar salud de API/PWA, worker sin cambios,
  smoke readonly y ningún torrent añadido al desplegar.
- Copia de código previa
  `~/viewtv-backups/ux-duplicados-descartados-pre-20261121-012822.tar.gz`
  SHA-256 `66137cc6da84a046a9a55931c08e9bab600cd7d45daf9f3a79a469c10da76cb2`.

## Uso

Recargar `http://127.0.0.1:3000` y abrir la
solicitud #4 para ver los dos resultados marcados
«Ya descartado». Para las alternativas de la
solicitud #6, «Descargar» permanece disponible
después de verificar automáticamente el .torrent,
siempre que el contenido sea correcto y autorizado.

La automatización de descarga está preparada,
pero no se ha probado la transferencia completa
de un archivo real. La organización en Jellyfin
sigue perteneciendo a otro hito.
