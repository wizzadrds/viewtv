# VIEWTV — clave TMDB activada y categorías reales comprobadas

**Fecha:** 22/11/2026, 02:04 (Europe/Madrid).
**Worktree autorizada:** `/home/viewtv/projects/viewtv-broker-0013-20261119`.
**Rama:** `viewtv-seguimiento-descargas-0012` · PR #2 OPEN/DRAFT.

## Objetivo y alcance

El propietario de ViewTV confirmó que ya había guardado su
**API Key v3 de TMDB** en el archivo privado productivo.
El cambio consistía exclusivamente en **recargar la API**, de modo
que las nueve filas de la portada desplegada previamente obtengan
metadatos reales (pósteres, fondo, títulos y fichas) **sin descargar
archivos de vídeo al explorar**.

## Diagnóstico previo de la clave (privacidad preservada)

- Antes de recrear el contenedor, el proceso productivo devolvía
  `TMDB_CONFIGURADA_EN_API=False`, porque las variables del contenedor
  no se recargan solas al editar `.env`.
- `scripts/viewtv_tmdb_clave_estado_privado_0013.py` verificó
  presencia **única**, formato hexadecimal de 32 caracteres v3
  y permisos privados del `.env` del propietario.
- Resultado: `TMDB_CLAVE_EN_ENV=API_KEY_V3_FORMATO_VALIDO`.
- **No se imprimió, guardó en un informe, versionó ni envió
  a GitHub el valor de la clave.** Los scripts solo exponen
  booleanos y recuentos.
- `scripts/viewtv_tmdb_consultas_reales_0013.py`, ejecutado
  en contenedor efímero bajo el control del propietario, con
  la configuración privada, obtuvo de TMDB v3 en directo:
  `TENDENCIAS_PELICULAS=19/19` con póster,
  `ESTRENOS_DEL_ANIO=20/20`,
  `ACCION=20/20`, `TERROR=20/20`,
  `SERIES=20/20`. Salió con código 0.

## Cambio aplicado en producción

Se creó una utilidad para reconfiguración **solo de API**:
`scripts/viewtv_tmdb_recargar_api_0013.sh`,
con comprobación de invariantes en
`scripts/viewtv_tmdb_compose_verificar_0013.py`.
Se verificó que el Compose resultante mantiene:

- API `viewtv:categorias-0013-api-conservative`.
- Frontend `viewtv-frontend:categorias-0013-candidate`.
- Worker `viewtv:release-0013-worker-candidate` sin cambios.
- Publicación Windows `general`, exclusivamente
  descargas verificadas con **ID mayor que 3**.
- API y worker con `/media` de **solo lectura**.
- Clave TMDB v3 presente en el environment de la API
  mediante `env_file`; no se imprimió su contenido.

Se pausó momentáneamente la tarea de Windows
`VIEWTV - Publicador automatico 0013` tras comprobar
`RunLevel=Limited`, inicio de sesión interactivo,
estado `Ready` y último resultado `0`.

Se ejecutó:

```shell
bash scripts/viewtv_tmdb_recargar_api_0013.sh check
bash scripts/viewtv_tmdb_recargar_api_0013.sh apply
```

La primera comprobación terminó `TMDB_COMPOSE_CLAVE_V3=CONFIGURADA`.
La segunda recreó **solamente `viewtv-api-1`**
con el mismo binario candidato y nueva variable de entorno.
**No se recrearon frontend, worker, Jellyfin ni FlareSolverr.**
No hay migración ni modificación manual de SQLite,
torrents ni archivos originales.

Después del cambio, dentro de la API:
`TMDB_CONFIGURADA_EN_API=True` y `IDIOMA_TMDB=es-ES`.
API y frontend siguieron `healthy`.
La CLI del publicador regresó
`{"estado":"listo","modo":"general","after_id":3,
"allowed_download_id":null}`.

La tarea Windows se reactivó y se lanzó un ciclo controlado.
Se verificó un ciclo posterior **código 0**:
`estado=correcto`, `publicacion=sin_trabajos`,
`catalogo=sincronizado`, con tarea `Ready`,
y la misma identidad limitada.

## Validación HTTP end-to-end de categorías reales

`scripts/viewtv_tmdb_filas_live_readonly_0013.py` corrió
en un **proceso de diagnóstico aislado** de la API;
usó TestClient y sobrescribió la dependencia de perfil
**solo en ese proceso**, sin cambiar autenticación real.
Todas las peticiones fueron GET: ninguna solicitud de descarga
ni operaciones sobre qBittorrent.

- `GET /descubrir/filas` sin sesión: **401**.
- `GET /descubrir/filas` en el proceso de prueba:
  **200** y `tmdb_configurado=true`.
- `recientes`: **4** fichas de biblioteca real,
  **4** con carátula; disponibles localmente.
- `peliculas-nuevas` (año actual, 2026):
  **20** entradas y **20** con carátula.
- `tendencias`: **19/19**.
- `accion`: **20/20**.
- `terror`: **20/20**.
- `comedia`: **20/20**.
- `ciencia-ficcion`: **20/20**.
- `series-tendencia`: **20/20**.
- `series-misterio`: **20/20**.
- Resultado global: `VIEWTV_TMDB_FILAS_REAL=9_OK`,
  `PRUEBA_CATEGORIAS_EXIT=0`.
- Smoke de producción existente: **10/10 PASS**
  (UI y proxy HTTP 200, autenticación protegida 401,
  Jellyfin disponible).

Estas pruebas comprueban la **respuesta real del backend**,
no sustituyen la comprobación visual del navegador del usuario.
Para cargar las filas actualizadas en sesión existente:
abrir `http://localhost:3000` y recargar con Ctrl+F5.

## Protección y límites funcionales

- El archivo `.env` privado del usuario queda en
  `/home/viewtv/projects/viewtv/.env` (fuera de la rama de desarrollo)
  y **NO se sube a GitHub**.
- La API solo solicita datos de TMDB **al abrir «Explorar»**,
  no descarga vídeos; tampoco existe aún una base persistente
  separada de metadatos remotos ni precarga nocturna.
- «Descargar» de una ficha remota crea **solo una solicitud**
  y remite a elegir una fuente autorizada.
- «Desinstalar» continúa **deshabilitado**, porque hace falta
  un mecanismo seguro para no borrar originales qBittorrent,
  romper hardlinks o perder datos de usuario.

## Copias e invariantes

Se conserva el respaldo SQLite online previo al primer
despliegue de categorías:
`/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-014729.db`,
SHA-256
`57aed7aca78bdc82261ddc0207cdcb4563807ca195e14223ca5e269a69e99d83`,
`PRAGMA integrity_check=ok`, FKs correctas, Alembic 0013.
No se restauró ni cambió.

Antes de editar los documentos de seguimiento se archivó:
`/home/viewtv/viewtv-backups/tmdb-activacion-docs-pre-20261122-020510.tar.gz`,
SHA-256
`c75065c036117f436df8d443d98f08f7d22f76a71e65d2a376e8f2228710442f`;
`tar -tzf` comprobado.

Si se revierte esta actualización de configuración:
no hay nuevos ficheros ni migraciones que restaurar;
recreando la API con la configuración anterior (sin clave)
se desactiva la consulta TMDB, sin afectar a los vídeos.
No cambiar la política general de publicación ni borrar
volúmenes o SQLite.

## Pendientes

1. Usuario: **confirmar visualmente** las categorías de
   2026, terror, acción y series con sus pósteres.
2. Mejora posterior: persistir metadatos remotos
   y actualizar periódicamente el catálogo con presupuesto
   y cuota TMDB; el sistema actual consulta bajo demanda.
3. Habilitar «Desinstalar» solo con autoridad de borrado
   separada, verificación de propiedad, inactividad y
   confirmación, protegiendo torrents ajenos.
4. Mantener PR #2 en borrador sin fusionarla por esta operación.
