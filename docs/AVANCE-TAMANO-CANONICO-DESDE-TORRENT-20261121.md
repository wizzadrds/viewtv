# VIEWTV — tamaño canónico obtenido del propio archivo .torrent

**Fecha:** 21/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`.
**Plan maestro:** [PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Motivo del cambio

El usuario detectó que el tamaño anunciado por Jackett no corresponde
al metainfo real en los dos candidatos comprobados («Nadie 2» y
«La Odisea»). Propuso que VIEWTV **use como fuente autorizada de
tamaño el propio archivo .torrent**, no los datos secundarios del
indexador. No se concluye que todos los indexadores estén equivocados;
solo se han comprobado los candidatos citados.

Ejemplo real de solicitud #6, resultado anunciado como
`La.Odisea.2026.4K.4K.SPANISH`: Jackett anuncia **20 GiB**
(21.474.836.480 bytes), pero metainfo indica
**33.260.748.236 bytes** (~33,26 GB decimales; ~30,97 GiB).
La coincidencia del título y tamaño del metainfo no garantizan
la identidad real del vídeo.

## Decisiones e implementación

- El backend mantiene `tamano_anunciado_bytes` solo como referencia,
  obtiene `tamano_real_bytes` mediante GET de metainfo `.torrent`
  desde el Jackett configurado (mismas restricciones existentes
  de origen, redirecciones, tamaño y tiempo).
- Una discrepancia de tamaño **no bloquea por sí sola**.
  Devuelve `estado=apto` con advertencia visible sobre la
  cifra de Jackett y el espacio requerido. Sí bloquea
  si no puede leer metainfo válido o si el infohash ya
  pertenece a un torrent descartado por ese perfil.
- `POST /solicitudes/{solicitud_id}/seleccion` vuelve a obtener
  metainfo ANTES de `BEGIN IMMEDIATE` para los URLs directos
  Jackett, conserva en la fila `descarga` el **tamaño real
  y el SHA-1 del bloque info** del torrent. No persiste
  el tamaño ni hash incorrectos del indexador para esos casos.
  Si el resultado cambia en DB antes del commit, se rechaza.
  La respuesta pública jamás expone hashes ni enlaces.
- La PWA **no muestra ninguna cifra de Jackett como si fuese
  tamaño real**: antes de verificar indica «Tamaño del torrent:
  por comprobar», después muestra el tamaño REAL como principal
  y la cifra de Jackett únicamente como comparación contextual,
  con advertencia no bloqueante cuando discrepan. Se mantiene
  el botón «Comprobar tamaño real» bajo demanda para evitar
  consultas de red masivas por cada refresco de resultados.
- `worker/download_processor.py` deja de bloquear por diferencia
  frente a Jackett. Comprueba el infohash si se guardó el
  canónico en la selección (detecta sustitución del metainfo),
  bloquea metainfo inválido y torrents descartados, y persiste
  tamaño/hash realmente leídos dentro del lease **antes de POST
  a qBittorrent**. Para la prueba de ID única en Windows,
  entrega el mismo enlace `.torrent` ya verificado en lugar
  de preferir otro magnet. Mantiene `stopped=true`, staging
  y filtros previos. No modifica el esquema SQLite.
- Enlaces de origen no verificable conservan compatibilidad
  legacy de API pero la PWA actual no permite seleccionar
  sin lectura de metainfo; la automatización general sigue
  inactiva. No hay un análisis de contenido del vídeo,
  comprobación de derechos ni reserva de espacio de disco.

## Validaciones

- Pruebas focales de solicitudes, procesamiento worker,
  prueba de alta única y parser bencode: **116/116 PASS**.
  Se añadieron aserciones de guardado de tamaño/hash canónicos,
  aviso no bloqueante por tamaño, descarte previo bloqueado,
  lectura no válida rechazada, cambio de hash bloqueado,
  `stopped=true` y sin enviar otros IDs. Se ajustaron
  fixtures antiguas al nuevo contrato.
- Suite completa backend **836/836 PASS**, solo dos
  avisos de deprecación no bloqueantes.
- Next.js compilado y TypeScript verificado **PASS**.
- Ensayo real `scripts/viewtv_tamano_canonico_copia_sandbox.py`
  con la copia SQLite productiva montada **solo lectura**,
  clonada en memoria y acceso solo de lectura al metainfo
  Jackett: **6/6 PASS**. Solicitud #6 se dejó
  `esperando_seleccion` únicamente dentro de la copia
  (la real ya estaba así tras deshacer selección).
  La PWA/API habría mostrado `apto` con advertencia
  por 20 GiB frente a 33,26 GB; la selección simulada
  guardó tamaño 33.260.748.236 bytes e infohash
  SHA-1 canónico y **0 intentos de descarga**.
  No se contactó con qBittorrent para enviar o iniciar.
- Imágenes instaladas, recreando **cada servicio por separado**
  con `--no-deps --no-build --force-recreate`:
  `viewtv:tamano-canonico-api-0012`,
  `viewtv-frontend:tamano-canonico-0012`,
  `viewtv:tamano-canonico-worker-0012`.
  Tres imágenes saludables/en funcionamiento.
- Preflight del Compose final comprobó:
  `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
  `VIEWTV_ENABLE_DOWNLOAD_START=false`,
  `VIEWTV_TORRENT_SUBMIT_DOWNLOAD_ID` vacía.
  Smoke readonly posterior **10/10 PASS**,
  endpoint protegido sin sesión **401**.
  Producción: solicitud #6 `esperando_seleccion`,
  cinco resultados aún disponibles, **0 descargas
  activas de #6 y 0 coincidencias de etiqueta de ID 2
  en qBittorrent**. No se envió ni se inició ninguna
  transferencia ni se modificó Jellyfin/medios.

## Respaldos

1. Código antes de los cambios:
   `~/viewtv-backups/usar-tamano-real-pre-20261121-005615.tar.gz`,
   SHA256 `7a158d1eacee0ee419db786bc8157d16d636b079b088a1f4ddb6090a819d87b3`.
2. SQLite coherente online antes de desplegar:
   `~/viewtv-backups/api-resultados-predeploy-20261121-010056.db.tar.gz`,
   SHA256 `a756dc9fb88fa1e363aa880a5c3a391cdd8595e4e3c06f42f7e92af167cfd59c`,
   `integrity_check` OK, `foreign_key_check` OK.
3. Informes antiguos respaldados antes de aclararlos:
   `~/viewtv-backups/corregir-informes-tamano-fuente-pre-20261121-010425.tar.gz`,
   SHA256 `14e0709408603a0c4e1c7b2136c5487cf7f40c82c475b92ac986043d5eeada31`.
   Todos los `tar.gz` se verificaron con `tar -tzf`.

## Próximo paso

El usuario puede recargar `http://127.0.0.1:3000`,
«Buscar y solicitar» → solicitud #6 → «Ver resultados»
→ «Comprobar tamaño real». El candidato que Jackett
mostraba como 20 GiB ahora se puede seleccionar
**con aviso de 33,26 GB reales**, siempre que no haya sido
descartado por infohash; no se ejecutará ningún
envío automático mientras los flags estén OFF.

**Hito separado:** seleccionar un candidato realmente correcto,
autorizado y con espacio disponible, probar su alta detenida e
inicio individual autorizado, progreso y finalización verificada
antes de habilitar la cola automática general.
Rollback independiente API/frontend/worker mediante
`scripts/viewtv_compose_tamano_canonico_0012.sh`;
PR #2 permanece draft, sin merge.
