# VIEWTV — impedir falsas coincidencias y limpiar «Mis solicitudes»

Fecha: 20/11/2026. **Rama exclusivamente**
`viewtv-seguimiento-descargas-0012`; PR #2 continúa draft.

## Incidencia real, objetivo y solución

El usuario pudo seleccionar en «Nadie 2» un resultado que era
`Cuando.nadie.nos.ve.S01E01...`, un capítulo de otra serie. La
descarga ID **1** de la solicitud **3** quedó en `seleccionada`,
0 %, sin hash de qBittorrent, sin intentos de envío. Los resultados
de Jackett no se pueden tratar como coincidencias verificadas:
de **62** guardados para esa solicitud, **solo 2** cumplen el nuevo
filtro conservador (título y tipo). Eso **no** valida los derechos
ni el contenido de esos dos candidatos.

Se corrigió la validación en tres capas del mismo release 0012:
- `backend/app/relevancia_resultado.py`: normaliza tildes,
  puntuación y números; exige correspondencia por prefijo completo
  de tokens; en películas excluye marcas de capítulo/temporada
  (S01E01, S01, 1x03) y rechaza años explícitos incompatibles.
  Con alias o traducciones sin correspondencia conservadora
  prefiere **no permitir una selección dudosa**.
- `worker/processor.py`: filtra *antes de guardar* y puede marcar
  `sin_resultados` si el proveedor trae solo coincidencias ajenas.
  `backend/app/solicitudes.py`: vuelve a validar al listar los
  resultados históricos y al hacer POST de selección (409 ante
  una coincidencia ajena).
- `frontend/components/requests-panel.tsx`: la lista principal
  consulta `GET /solicitudes?solo_activas=true`. Al seleccionar
  desaparece de pendientes. «Ver historial» permite consultar las
  ya finalizadas/fallidas, sin mezclarlas en la lista diaria.
  **No se borró el historial de SQLite.**

Para corregir elecciones accidentales, se añadió
`POST /solicitudes/descargas/{id}/deshacer-seleccion` y botón
«Deshacer selección» en `downloads-panel.tsx`. La API permite el
deshacer **solo** al perfil propietario, con la descarga todavía
`seleccionada`, 0 %, sin hash de qBittorrent, sin envíos ni leases y
sin inicio; en transacción inmediata elimina **esa selección nunca
enviada** y reabre la solicitud con sus resultados conservados.
Rechaza el resto con 409 o 404. El botón requiere confirmación
expresa del usuario. Se ajustó el estado para dejar claro que
«seleccionada» **no equivale a descarga iniciada**.

**La selección equivocada ID 1 no se ha deshecho de producción por
el conector:** permanece hasta que el usuario pulse el botón
«Deshacer selección» en la PWA. No se han iniciado ni registrado
torrents con esa ID. Al reabrirla, los resultados visibles serán
solo los que pasen el filtro; el usuario verificará manualmente
el contenido y sus derechos antes de elegir.

## Evidencias de pruebas

- Backend completo con el entorno virtual existente:
  **778 pruebas aprobadas**, 2 advertencias ajenas de deprecación.
  Incluye tests de filtrado de episodios, solicitud activa/historial,
  selección incorrecta rechazada, deshacer seguro y aislado por
  perfil, y caso de worker con proveedor simulado.
- Build Next.js del frontend: **correcto**, TypeScript y lint
  correctos, imagen `viewtv-frontend:relevancia-0012`.
- Ensayo en imagen API con fechas de Jackett: **3/3 PASS**;
  imagen worker con flujo sintético completo: **6/6 PASS**;
  ambos sin red, con SQLite en memoria.
- **Ensayo de extremo a extremo sobre COPIA real en SQLite en
  memoria** montada desde respaldo ro y sin red:
  **4/4 PASS**: deshacer la selección incorrecta (solo en copia),
  ocultar el episodio, impedir elegirlo de nuevo mientras sí se
  admite un candidato de título coincidente, y quitar la petición
  completada de la lista de pendientes.
- Lectura de producción con volumen ro y PRAGMA query_only:
  62 resultados almacenados en solicitud #3, solo 2 coincidentes;
  selección #1 reversible, sin envío ni hash.
- Postdespliegue de solo lectura: **10/10 PASS**, API, frontend y
  Jellyfin saludables; API y frontend accesibles en loopback;
  nuevas rutas sin sesión dan **401**; worker en ejecución.
  Flags reales: `VIEWTV_ENABLE_TORRENT_SUBMIT=false`,
  `VIEWTV_ENABLE_DOWNLOAD_START=false`, ID autorizada vacía.

## Copias de seguridad verificadas antes de escribir/recrear

- Código, tests, frontend y plan previo:
  `~/viewtv-backups/corregir-relevancia-limpiar-ui-20261120-231753.tar.gz`.
  SHA-256 `f904ed1c4184f330413d4752836c72b2edb49b717dc8a8d62a05a7d87e420c7e`.
- Test del worker previamente existente:
  `~/viewtv-backups/test-serie-relevancia-20261120-232312.tar.gz`.
  SHA-256 `66eaac28489838ef7d56c22a6bb28700c81dc1b2f78963f6a1269109a98364de`.
- SQLite real, copia online coherente realizada desde volumen
  **montado solo lectura** con `sqlite3.Connection.backup`,
  `PRAGMA integrity_check=ok` y `foreign_key_check=0`:
  `~/viewtv-backups/api-resultados-predeploy-20261120-232434.db.tar.gz`.
  SHA-256 `557f9f342e2ef8612a1b3bb0d6887207c9fa7535db3faa3929c716672397f011`.
  Todas las copias fueron verificadas con `tar -tzf`.

No se restauraron ni editaron bases de datos productivas ni medios;
la copia de SQLite fue solo lectura sobre el origen. No se
leyeron PIN, cookies, hashes ni enlaces de torrents en las salidas.

## Despliegue controlado y reversibilidad

Imágenes finales:
- API `viewtv:relevancia-api-0012` sobre `viewtv:resultados-fecha-0012`.
- Worker `viewtv:relevancia-worker-0012` sobre
  `viewtv:inicio-torrent-unico-0012`, conservando sus guardas.
- PWA `viewtv-frontend:relevancia-0012`.

Sin migraciones ni cambios de esquema 0012. Se conservaron todos
los overlays existentes, se comprobó el Compose final y se recreó
**cada servicio por separado** mediante
`--no-deps --no-build --force-recreate`.
No se modificó FlareSolverr ni Jellyfin.

Reproducción y rollback: desde el worktree autorizado ejecutar
`bash scripts/viewtv_compose_relevancia_0012.sh preflight`,
`deploy-api`, `deploy-worker`, `deploy-frontend`, o para
volver a las imágenes anteriores:
`rollback-api`, `rollback-worker`, `rollback-frontend`.
Hacer rollback individual si falla salud; **no restaurar SQLite**
(sin migración), no usar `docker compose down -v`, no fusionar PR #2.

## Pendientes reales

1. Usuario recarga PWA y confirma «Mis solicitudes (pendientes)»
   limpio y «Ver historial» accesible.
2. Usuario pulsa «Deshacer selección» en la descarga #1 y
   confirma; esta es una escritura explícita y transaccional
   de **su propia selección no enviada**. La reversión de esa
   operación de usuario es volver a seleccionar un candidato.
3. Usuario revisa los dos candidatos de título coincidente y
   selecciona material que tenga derecho a obtener. El filtro
   no demuestra autenticidad, derechos ni que sea película real.
4. Para el ensayo de **una sola descarga** elegir un
   `download_id` canónico y pedir permiso independiente
   de **añadir detenido**; solo después permiso independiente de
   **iniciar**. No se han habilitado envíos ni descargas reales.
