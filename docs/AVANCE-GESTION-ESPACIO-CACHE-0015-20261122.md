# VIEWTV 0015 — Gestión de espacio, caché y películas vistas

**Fecha:** 22/11/2026, Europa/Madrid.
**Rama:** `viewtv-seguimiento-descargas-0012`, PR #2 abierto y en borrador.
**Orden confirmado por el propietario:** terminar la gestión del espacio, caché y retirada de películas ya vistas **antes de desarrollar la app Samsung profesional**. La idea futura «VIEWTV Momentos» va después de la app.

## Resumen ejecutivo: alcance real

Implementado y desplegado un **primer hito no destructivo** de gestión de espacio para la PWA actual:

1. Nueva sección **«Espacio»** tras iniciar sesión en la interfaz principal (`/`), con libre en volumen, tamaño lógico de películas, descargas temporales, caché y fichas TMDB.
2. **Marcar/desmarcar películas como vistas** para cada perfil ViewTV; estado persistente en SQLite, no inferido del historial de Jellyfin.
3. **Solicitar la retirada de una película marcada como vista** con doble confirmación y título exacto; se puede cancelar. Esta solicitud **NO borra ningún archivo**, no cambia qBittorrent y queda a la espera de autorización y ejecución segura en Windows.
4. **Limpieza restringida** de archivos `viewtv-<hex>.tmp` en una subcarpeta privada `/cache/viewtv-temporales` con marcador exacto `.viewtv-cache-v1`. Si la carpeta propia no existe, no borra nada. No limpia la caché de Jellyfin, la SQLite TMDB ni medios.
5. La nueva interfaz muestra expresamente que los tamaños lógicos **no** son espacio físico recuperable si el original y la película están unidos por hardlinks.

**No se ha habilitado el borrado físico de una película.** La petición del usuario de poder eliminar películas vistas **sigue abierta** para el siguiente hito dentro de la gestión de almacenamiento, no para el trabajo de la app Samsung. No afirmar que ya se liberan gigabytes.

## Inventario real anterior y posterior al despliegue

Diagnóstico con rutas autorizadas **solo lectura**, sin mostrar nombres de películas:

- Carpeta general de medios `C:\VIEWTV\media`: aprox. **25 GB**.
- Biblioteca `/media/Peliculas`: **24,31 GiB**, **4 archivos**, recorrido completo.
- Carpeta de descargas originales `/media/descargas_temporales`: **24,31 GiB**, **8 archivos**, recorrido completo.
- **No sumar** esas dos cantidades: la publicación Windows utiliza **hardlinks NTFS** y potencialmente representan los mismos datos físicos. No se infiere espacio recuperable de las cifras. Las rutas de ambos subárboles se montan `/media:ro` en API y worker.
- Caché `/cache` montada: **0 GiB, 0 archivos**, sin subcarpeta propia marcada para limpieza.
- Disco con esa caché y medios: aproximadamente **705,5 GiB libres** (antes ~706 GB según `df -h`); el volumen completo contiene **otros datos ajenos a ViewTV**.
- Cuota existente `cache_quota_gb=80` en `backend/app/config.py`: **configurada pero NO aplicada de manera global**. El panel la llama «configurada» y no promete límites de Jellyfin ni de otros programas.
- Fichas de TMDB: SQLite separada `/catalogo/metadatos.db` solo lectura en la API; el catalogador ya depura **metadatos caducados a 150 días**, sin vídeos ni borrado de carpetas de medios.

El estado de la SQLite tras despliegue es `0015_gestion_espacio_vistas`, integridad `ok`, claves foráneas correctas, **0 marcas manuales y 0 solicitudes de retirada** al efectuar esta lectura; no se marcaron ni borraron películas del usuario para probar.

## Implementación

### Backend y permisos

- `backend/app/almacenamiento_archivos.py`: contador limitado (máximo 100.000 entradas y profundidad 12), sin seguir enlaces simbólicos ni recorrer otro dispositivo, con `completo=false` si faltan datos. El contador deduplica inodos dentro del mismo subárbol, pero **no afirma deduplicación física entre carpetas**. Solo temporales descartables de nombre estricto, propietario correcto, un único hardlink y directorio privado con marcador se pueden limpiar; no borra carpetas ni archivos con extensiones de vídeo.
- `backend/app/almacenamiento.py`: todas las rutas autenticadas por `get_current_profile`. No devuelve rutas, hashes de torrent, tokens ni títulos de otros perfiles. No recibe rutas de archivos desde el cliente ni permite eliminarlas.
- `GET /almacenamiento/resumen`: información agregada del volumen, bibliotecas y caché, distingue cuota configurada de cuota realmente aplicada.
- `GET /almacenamiento/peliculas?limit=20&offset=0`: películas disponibles y marcas/solicitudes del **perfil actual**; series excluidas, paginación y límite estrictos.
- `POST /almacenamiento/peliculas/{id}/visto`: JSON `{"visto":true|false}`; el booleano es estricto; desmarcar con retirada pendiente devuelve **409** hasta que se cancele.
- `POST /almacenamiento/peliculas/{id}/retirada`: exige que esté vista en ese perfil, película local disponible y `titulo` idéntico al del catálogo. Devuelve **202, pendiente_revision**. No hay procesador que borre archivos.
- `DELETE /almacenamiento/peliculas/{id}/retirada`: cancela una retirada pendiente sin tocar medios.
- `POST /almacenamiento/cache/limpiar`: exige confirmación `LIMPIAR TEMPORALES`; elimina solo temporales identificados como propios, si existe directorio privado válido; no se usó contra la cache productiva durante pruebas.
- No se cambian los flujos existentes de búsqueda, descarga, reproducción o publicación Windows, ni se activan opciones globales de envío.

### SQLite 0015

`backend/migrations/versions/0015_gestion_espacio_vistas.py`, aditiva desde 0014:
- `pelicula_vista` con `(perfil_id, medio_id)` único y fecha.
- `solicitud_retirada` con `(perfil_id, medio_id)` único; estados `pendiente_revision` o `cancelada`, fechas de auditoría.
- Downgrade **solo si ambas tablas están vacías**: cuando existan marcas o peticiones se niega a borrar información. Para reversión operativa se conserva esquema 0015.
- No se migraron registros históricos para adivinar que una película ya ha sido vista. El usuario la marca expresamente.

### Interfaz

- Nuevo `frontend/components/storage-panel.tsx` y estilos en `frontend/app/globals.css`.
- Menú **«Espacio»** integrado en `frontend/components/viewtv-app.tsx`; muestra tarjetas de ocupación, listado paginado, filtro local, marcas de visto, solicitud/cancelación, información de retirada pendiente, mensajes accesibles y control de caché.
- **El botón dice «Solicitar retirada»**, no «Borrar», y utiliza confirmación del título + `window.confirm`.
- Se mantiene la navegación por foco/teclas del mando de la PWA. No se ha probado aún físicamente en Samsung.
- La web compatible `/tv.html` **no fue modificada** y puede seguirse utilizando para explorar y reproducir mientras se planifica la app instalable. El menú nuevo aparece en la **PWA principal**, no en `/tv.html`.

## Pruebas y respaldo

- Respaldo de fuentes previo a cambios:
  `/home/viewtv/viewtv-backups/gestion-espacio-cache-pre-20261122-224320.tar.gz`;
  SHA-256: `cd32ed2cf5ffa9041d06e2d4564cec44ce059506e8d9c2760d50b55fd78b8ca8`.
  `tar -tzf` **PASS**, incluye backend/main/models, frontend, pruebas, documentos, despliegue anterior y migración 0014, sin `.env` ni `.bak`.
- Copia SQLite productiva online **antes del despliegue**:
  `/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-225105.db`;
  SHA-256 `ac0352f867deae7d3336ef6c92cbe33049d1d7de75de56b25da5a80b13d32e30`.
  Respaldo **PASS**, `PRAGMA integrity_check=ok`, `foreign_key_check=[]`. Permisos 0600, sin mostrar cuentas.
- Ensayo de migración **con un clon real temporal**, contenedor sin red:
  **0014 → 0015 → 0014 → 0015**, integridad y FK PASS y recuentos idénticos de `perfil`, `medio`, `solicitud` y `descarga`. Script: `scripts/viewtv_gestion_espacio_migracion_clone_0015.py`.
- Suite backend completa **1017/1017 PASS**, 2 avisos de deprecación externos. Incluye 11 regresiones nuevas: permisos, aislamiento por perfil, requisito de visto, confirmaciones, cancelar, booleano estricto, caché con archivo simbólico/hardlink y ausencia de borrado de directorios ajenos.
- Frontend: **18/18 pruebas Node PASS**, TypeScript `tsc --noEmit` PASS, ESLint ejecutado correctamente desde la raíz del frontend sin errores, Next.js **build de producción PASS** con ruta raíz estática.
- Ruff para los archivos nuevos y modificados: **PASS**.
- Cuatro imágenes backend 0015 construidas sin red: API y worker nuevos; API y worker de rollback que mantienen las nuevas tablas. Frontend construido como `viewtv-frontend:gestion-espacio-0015`.
- Preflight Compose y hashes de respaldos PASS; se conserva el catalogador, el publicador y la política de envío/inicio de torrent desactivado. Antes de aplicar, **cero solicitudes procesándose y cero descargas activas**.
- Despliegue limitado: recreadas exclusivamente API, worker y frontend; ambos backends reconocen `alembic head=0015`, API y frontend **healthy**. Jellyfin, catalogador y servicio Windows **no recreados**.
- Smoke posterior de solo lectura **10/10 PASS**. `GET /almacenamiento/resumen` sin cookie → **401**; `GET /api/viewtv/almacenamiento/peliculas` sin cookie → **401**; `http://192.168.1.138:3000/tv.html` → **200**. Esto no prueba funcionalmente el panel autenticado en el TV real.
- Postdespliegue: SQLite `0015_gestion_espacio_vistas`, integridad `ok`, FK `OK`, **0 descargas activas** y **0 solicitudes procesándose**. `scripts/viewtv_gestion_espacio_live_readonly_0015.py` consultó los totales sin escribir.

## Reversión segura

`scripts/viewtv_gestion_espacio_deploy_0015.sh check-rollback` **PASS**: Compose efectivo validado, imágenes compatibles y medios solo lectura. Están preparadas `viewtv:gestion-espacio-rollback-api-0015` y `viewtv:gestion-espacio-rollback-worker-0015`. La imagen de frontend previa se conserva intacta.

Ante regresión crítica, desde la rama autorizada, después de revisar estado y copias:

```bash
bash scripts/viewtv_gestion_espacio_deploy_0015.sh rollback
```

Esto revierte **la lógica y la interfaz** recreando solo los tres servicios, **sin bajar el esquema SQLite 0015 ni borrar vistas o solicitudes**. El rollback no se ejecutó en producción.

## Pendiente imprescindible antes de la app Samsung

El usuario pide **eliminar realmente películas vistas para liberar espacio**. Hoy existe la marca de vista y la petición de retirada, pero **NO** hay un ejecutor autorizado; se mantiene el borrado de producción bloqueado por seguridad. El hito siguiente de **esta misma tarea de almacenamiento** es:

1. **Resolver propiedad sin heurísticas de nombres**: correlación inequívoca entre `medio.id` y Jellyfin ID, el manifiesto privado del publicador Windows y la `descarga.id` verificada. No basta igualar texto del título.
2. Verificar que la película pertenece exclusivamente a VIEWTV, que el video está en la raíz Windows aprobada, los inodos/enlaces duros y la existencia de **otros enlaces**. Validar torrent registrado y consultar el estado de qBittorrent sin tocar torrents ajenos; no eliminar si está descargando, verificando o en uso. No descargar ni iniciar nada para probar.
3. Requerir autorización del **administrador de la biblioteca compartida**, porque una marca de visto individual no autoriza borrar para todos los perfiles. Confirmación adicional con título, tamaño y consecuencias; estado de revisión, cancelación y un registro durable protegido.
4. Ensayar en un **sandbox NTFS aislado**: confirmación doble, denegación por reparse/symlink, hardlinks compartidos, archivo abierto, torrent activo, cambio de identidad, falta de espacio, fallo Windows y recuperación sin corrupción.
5. Implementar, tras demostrar la autoridad y con aprobación explícita, el ejecutor Windows de retirada, con bloqueo del contenido afectado, verificación inmediatamente anterior y posterior, y escaneo/sincronización Jellyfin. Reportar **bytes realmente liberados**, no tamaño lógico ni suposición por hardlink.
6. Incorporar control de cuota/caducidad a los temporales reales **cuando existan escritores autorizados**, no simplemente borrar contenido desconocido bajo `/cache`. La cuota de 80 GiB actual es informativa, no aplicada.
7. Probar con el propietario la página autenticada «Espacio» desde navegador normal; la versión Samsung compatible sigue sin este menú, hasta la futura app instalable.

**Solo cuando la retirada física segura y sus pruebas estén terminadas** debe pasarse a la app Samsung profesional, y después a «VIEWTV Momentos».

## Qué se hizo, qué se supuso, qué queda

**Hecho:** seguimiento por perfil, panel de ocupación, solicitudes de retirada cancelables, limpieza limitada de temporales propios, modelo 0015 y despliegue reversible, pruebas y respaldo. No se borraron medios ni torrents.

**Supuestos:** los tamaños del sistema operativo son tamaños lógicos. Distintos hardlinks pueden compartir bytes físicos. Una película marcada como vista lo está porque el usuario lo indica manualmente; no se infiere de Jellyfin.

**Pendiente:** ejecución física autorizada en Windows, cuota de caché efectiva, prueba manual autenticada y futura integración en app Samsung. Estos puntos siguen abiertos en BACKLOG y no se reportan como completados.

## Seguimiento 0016 (22/11/2026)

La fase posterior confirmó dos publicaciones propias con diario,
huella y hardlink NTFS válidos, dos rutas exactas de Jellyfin
y dos torrents qBittorrent aún **en uso**; hay una carpeta
sin diario verificable que no debe tocarse. Se corrigió
además el rechazo del publicador Windows ante Alembic 0015.
No se han borrado películas.

Ver [AVANCE-AUDITORIA-RETIRADA-SEGURA-0016-20261122.md](AVANCE-AUDITORIA-RETIRADA-SEGURA-0016-20261122.md).
