# VIEWTV 0024 — Revisión segura por película tras solicitud de retirada

**Fecha:** viernes 27 de noviembre de 2026, Europe/Madrid.
**Repositorio:** `wizzadrds/viewtv`; rama `viewtv-seguimiento-descargas-0012`.
**PR #2:** OPEN, DRAFT, sin fusionar.
**Estado:** herramienta local exclusivamente de lectura, sin cambios de producción ni borrados.

## Situación y objetivo

Un perfil puede marcar una película como vista y solicitar que se retire. La interfaz confirma entonces **«Retirada pendiente de revisión · archivo intacto»**. Esa solicitud es válida como **petición del perfil**, pero no es una autorización del administrador de la biblioteca compartida. Otro perfil puede no haber marcado la película como vista; además, qBittorrent y Windows pueden seguir utilizando los originales.

La auditoría inicial 0023 verificó cuatro películas sin permiso de retirada y un único caso con petición válida (tres carecían de petición). El objetivo 0024 es **confirmar inequívocamente la película concreta y su año**, cruzar la nueva solicitud y su marca «vista» con el preflight técnico y explicar los bloqueos sin revelar identidades de perfiles ni actuar sobre archivos.

La ejecución real verificó una película con petición activa, su marca «vista» en un perfil y un segundo perfil todavía sin marcarla vista; el torrent relacionado permanece activo según el estado de preflight y contiene archivos no verificables para eliminación total. No se guarda en este documento el título, el nombre de los perfiles, IDs privados de Jellyfin, hash de torrent, rutas NTFS ni fechas individuales. El caso real se informó al usuario de manera privada en la conversación.

## Cambios de código

### 1. Revisión de la solicitud dentro de la API, solo SELECT

`scripts/viewtv_retirada_solicitud_api_0024.py`:
- Ejecutable como código introducido por `docker exec -i viewtv-api-1 python - <titulo> <anio>`; **no instala endpoints ni altera la imagen Docker**.
- Exige coincidencia de **título exacto, año, tipo película y disponibilidad** en SQLite; con cero o más de una coincidencia **no selecciona nada**.
- Lee perfiles activos, marcas individuales `pelicula_vista` y `solicitud_retirada` mediante `select`; excluye perfiles inactivos y detecta duplicados/estados no reconocidos.
- Devuelve JSON privado al orquestador local, que **no reenvía títulos, IDs de perfil, Jellyfin ni rutas al usuario ni a GitHub**.
- No invoca `POST`, `UPDATE`, `DELETE`, `commit`, qBit de escritura ni ninguna función de retiro.

### 2. Revisión cruzada de petición y capacidad física

`worker/retirement_request_review_0024.py`:
- Comprueba que **medio_id y jellyfin_id** corresponden exactamente entre la consulta a SQLite y el snapshot integrado SQL/Jellyfin/qBit de 0018.
- Contrasta las listas completas de perfiles activos, perfiles con «vista» y solicitudes pendientes; **si la situación cambió entre consultas, aborta**.
- Requiere exactamente una fila de preflight por película, con `estado=bloqueada`, `puede_borrarse_ahora=false` y el motivo obligatorio `falta_autorizacion_administrador`.
- Confirma que los motivos `hay_perfiles_sin_marcar_vista` y `sin_peticion_valida_de_retirada` concuerdan con las listas SQLite. Una solicitud válida de un perfil no se convierte en permiso de toda la biblioteca.
- Devuelve únicamente contadores agregados, estado `pendiente_revision_bloqueada` / `sin_peticion_valida` y los motivos técnicos. **Siempre** fija `autoriza_borrado_fisico=false`, `aprobacion_administrativa_emitida=false` y cero operaciones de modificación.

### 3. Diagnóstico local por película, dos verificaciones

`scripts/viewtv_retirada_revision_solicitud_0024.py`:
- Acepta el título y año de una película para revisión únicamente local, sin abrir ninguna operación destructiva.
- Consulta evidencia NTFS Windows **antes y después**, consulta SQLite por la película **dos veces**, lee snapshot integrado y diarios de publicación privados mediante `O_NOFOLLOW`, y ejecuta el preflight.
- Rechaza cualquier cambio entre las dos lecturas, inconsistencia de identidad, fallo de docker/Windows, timeout o respuestas incorrectas.
- **Nunca muestra títulos, rutas, hashes, nombres/IDs de perfiles, tokens ni datos de otras películas**. En caso de error solo indica que la evidencia no es confiable y que no hay permiso.
- Una consulta no concede bloqueo transaccional continuo; puede iniciar una reproducción o modificarse un torrent inmediatamente después. **No autoriza retirar archivos.**

## Prueba en el equipo real

La consulta local encontró **una película inequívoca**, con una solicitud pendiente de revisión coherente con su marca de vista:

- **Perfiles activos:** 2.
- **Perfiles con «vista»:** 1.
- **Perfiles sin «vista»:** 1.
- **Solicitudes de retirada pendientes:** 1 (válida).
- **Estado:** `pendiente_revision_bloqueada`.
- **Motivos de bloqueo:** falta autorización del administrador; al menos un perfil aún no la ha marcado vista; torrent activo o incompleto según guard; listado de archivos qBit no verificable para retirada.
- **Aprobación emitida:** NO.
- **Permiso de borrar:** NO.
- **Archivos eliminados:** 0; **torrents modificados:** 0.

**No se debe cambiar unilateralmente el estado «vista» del otro perfil, detener un torrent o autorizar una retirada para convertir los indicadores en verdes.** Cada perfil es independiente; la aprobación administrativa es un paso diferente y debe otorgarse expresamente cuando se garantice que no se daña contenido compartido.

## Verificaciones

- `backend/tests/test_retirada_solicitud_0024.py`: casos sintéticos de un perfil visto y otro pendiente, solicitudes canceladas, duplicados, identidad Jellyfin, listas de perfiles ambiguas y cambios de estado.
- `backend/tests/test_retirada_revision_runner_0024.py`: tests con fuentes inyectadas, dos consultas SQL/NTFS, variaciones entre lecturas, fallo cerrado, filtrado de datos privados, timeouts y prueba de que el script SQL no modifica la base.
- **43/43 tests específicos PASS** y Ruff PASS.
- **Smoke de lectura 10/10 PASS. Suite backend general 1312/1312 PASS**, con dos advertencias de deprecación de dependencias externas; ejecutada en contenedor de tests sin red.
- Producción sin cambios de imágenes ni migraciones, sin modificar qBit, Jellyfin, Windows, SQLite o ficheros. No se creó clave admin 0019 ni ticket de borrado.

## Copia previa

Backup validado **antes** de cualquier edición de fuentes/documentos existentes:
`/home/viewtv/viewtv-backups/retirada-solicitud-0024-pre-20261127-165426.tar.gz`,
SHA-256 `1d8a92ec344e7a2a4edbe60b1d9df8e1710d7519c704934660119671c46ac430`,
`tar -tzf` PASS. Exclusivamente código y documentos anteriores; sin claves, bases de datos, diarios de publicación ni películas.

## Continuación necesaria

1. Mantener esta solicitud como `pendiente_revision` y **no convertirla en eliminación automática** por una marca «vista».
2. Resolver de modo independiente las garantías para **los demás perfiles**, sin manipular sus marcas.
3. Corregir la política de coexistencia de **los metadatos extra de qBittorrent**; no eliminarlos ni detener torrents sin consentimiento por título y propiedad exclusiva comprobada.
4. Actualizar el publicador Windows antiguo con mutex de forma **supervisada**, tras respaldo, deshabilitación de tarea y comprobación de no trabajo activo (diagnóstico 0023).
5. Construir reserva real sobre inicio de sesiones/streams Jellyfin y escrituras qBit; meter autoridad 0019 y journal 0020 en un único ejecutor Windows con revalidación, recuperación y medición de bytes físicamente liberados.
6. **Solo después** retirar una película concreta autorizada con prueba de bytes recuperados. Después app Tizen Samsung profesional y «VIEWTV Momentos».

**No se ha borrado ninguna película real.**
