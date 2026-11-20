# VIEWTV — solución del HTTP 500 al abrir resultados de búsqueda

**Fecha:** 20 de noviembre de 2026. **Rama:** `viewtv-seguimiento-descargas-0012`.

## Problema real y causa demostrada

El usuario ha creado desde «Buscar y solicitar» una nueva solicitud de
«Nadie 2» que aparece como **Resultados disponibles**, pero al pulsar
«Ver resultados» la PWA mostraba **Error HTTP 500**, sin botones de
selección. No era un fallo de Jackett ni de la interfaz de selección:
el log de `viewtv-api-1` mostró `ResponseValidationError` en
`GET /solicitudes/{solicitud_id}/resultados`, con varios valores
`publicado_en` de tipo `datetime` que FastAPI no admitía bajo
la anotación `list[dict[str, int | str | list | None]]`.

**Solución mínima:** `backend/app/solicitudes.py` convierte
`resultado.publicado_en` mediante `.isoformat()` o devuelve `None`.
No se cambió el modelo, la migración, el filtro de perfiles, el
orden de calidades, las URLs del proveedor ni la selección.
`backend/tests/test_solicitudes.py` incluye una regresión con fecha.

## Pruebas de corrección (hechas, sin credenciales)

1. `scripts/viewtv_resultados_fecha_sandbox.py`, contenedor
   aislado sin red, filesystem de solo lectura y SQLite en memoria:
   **HTTP 200 con fecha real**, **fecha nula admitida** y
   **sin URL/magnet/hash internos**. Pasaron **3/3**.
2. Imagen `viewtv:resultados-fecha-0012` construida desde
   `viewtv:predeploy-0012-release` copiando únicamente
   `backend/app/solicitudes.py`. El mismo ensayo sobre la
   imagen construida volvió a pasar **3/3**.
3. `scripts/viewtv_resultados_copia_sqlite_readonly.py` ejecutado
   con una **copia previa de SQLite real montada solo lectura**,
   en contenedor sin red y con perfil autenticado simulado:
   **HTTP 200**, **número de resultados conservado**, **sin
   exposición de datos internos**. No se consultó PIN ni cookie;
   solo se publicaron contadores/veredictos, no títulos ni enlaces.
4. Despliegue real: `viewtv-api-1` recreado **solo** con
   `docker compose up -d --no-deps --no-build --force-recreate api`.
   Imagen final `viewtv:resultados-fecha-0012`, **healthy**,
   salud directa y por proxy **200**, la ruta privada sin sesión
   sigue dando **401**, smoke de solo lectura **10/10 PASS**.
   Worker `viewtv:inicio-torrent-unico-0012` y frontend
   `viewtv-frontend:solicitudes-0012` siguen sin recrear.

**Pendiente:** una comprobación desde la sesión auténtica del
usuario de que «Ver resultados» muestra candidatos y sus botones,
seguida de selección explícita de material autorizado y seguimiento.
No se afirma que las coincidencias correspondan realmente a la película;
no se ha hecho ninguna selección ni añadido torrents desde el conector.

## Respaldos previos comprobados

- Código, test y plan: `~/viewtv-backups/error500-resultados-20261120-230130.tar.gz`.
  SHA-256 `c1390b1a11195bd9fa09fcbf2469b5b62a6e687753d37297fbe7d011c33716eb`;
  `tar -tzf` mostró los tres archivos preexistentes.
- Base activa antes del recreado: copia coherente mediante
  `sqlite3.Connection.backup` desde volumen de datos montado
  **solo lectura** a una ruta privada, con `integrity_check=ok`
  y `foreign_key_check=0`; tar `~/viewtv-backups/api-resultados-predeploy-20261120-230358.db.tar.gz`.
  SHA-256 `423684408ade952166b89a1700d22cb598326728e9af1fc204274801ad69a392`;
  `tar -tzf` confirmó `api-resultados-predeploy-20261120-230358.db`.
  La base productiva **no** se restauró ni modificó manualmente.

## Imagen, despliegue y reversión sin datos

Archivos:
- `deploy/Dockerfile.resultados-fecha-0012`
- `deploy/compose.resultados-fecha-0012.yaml`

Se reconstruyó desde el worktree autorizado, se validó el contrato
de Compose y se recreó exclusivamente la API. Las cuatro capas
originales de Compose se mantienen:

```bash
cd /home/viewtv/projects/viewtv
docker compose -f compose.yaml -f compose.production.yaml \
  -f /home/viewtv/viewtv-backups/compose-verification-enabled.yaml \
  -f compose.release-0012.yaml \
  -f /home/viewtv/projects/viewtv-broker-0013-20261119/deploy/compose.resultados-fecha-0012.yaml \
  up -d --no-deps --no-build --force-recreate api
```

**Rollback inmediato si la API se degrada:** repetir el comando
anterior **sin el quinto override**. Esa capa base usa
`viewtv:predeploy-0012-release`. Verificar después `/health`,
acceso por proxy y que los servicios worker/frontend no se recrearon.
La reversión de imagen **no requiere restaurar SQLite** porque no
hubo migración ni cambio de esquema. No usar `docker compose down -v`,
`git reset --hard`, borrados ni reorganización de bibliotecas.

El envío de torrents, el inicio y el organizador permanecen
desactivados/limitados; no se han tocado medios ni qBittorrent.
La PR #2 sigue en borrador y no se fusiona.
