# Cierre de jornada ViewTV — 22/11/2026

**Estado a las 23:19 (Europa/Madrid): jornada cerrada, sin tareas pendientes ejecutándose por el asistente.**
**Rama única:** `viewtv-seguimiento-descargas-0012` del repositorio `wizzadrds/viewtv`.
**PR #2:** mantener **OPEN / DRAFT / NO MERGE**; base `inventario-trabajo-local`.
**Último commit funcional de la sesión antes de este cierre:** `37d87ee` (auditoría retirada NTFS y reparación publicador).
**Último commit anterior:** `d6a9338` (gestión del espacio, caché y vistas).
**Regla:** no ejecutar borrados físicos de películas ni de torrents sin comprobaciones de titularidad, derechos sobre el material, administrador y aprobación concreta.

## 1. Trabajo completado y desplegado

- Interfaz principal de ViewTV `http://192.168.1.138:3000/`: sección **Espacio** para consultar ocupación, marcar/desmarcar películas vistas por perfil, solicitar retirada con doble confirmación y cancelar solicitudes. Su botón es **Solicitar retirada**, **NO** «Eliminar».
- La limpieza disponible solo contempla temporales descartables propios marcados. En el servidor la caché actualmente está vacía, por lo que **no ha liberado espacio real**. El valor de cuota configurada de **80 GiB** no equivale a una cuota aplicada globalmente.
- Estado del disco leído desde la API: aproximadamente **705,5 GiB libres**. Biblioteca `/media/Peliculas`: **24,31 GiB en cuatro archivos**; descargas originales `/media/descargas_temporales`: **24,31 GiB en ocho archivos**. Son tamaños lógicos y **NO se suman** porque pueden compartir bloques mediante hardlinks NTFS.
- Base SQLite en migración **0015_gestion_espacio_vistas**, integridad `ok` y claves foráneas correctas tras actualizar. La migración aditiva se ensayó en clon real `0014→0015→0014→0015`.
- Detectado y **corregido** rechazo del comando interno del publicador Windows tras migraciones SQLite 0014/0015. El comando de estado vuelve a responder `listo` en modo `general` con límite histórico `after_id=3`, manteniendo validación estricta de columnas y revisiones.
- En producción están en marcha y saludables: API `viewtv:publicador-compatible-api-0016`, frontend `viewtv-frontend:gestion-espacio-0015`, worker `viewtv:gestion-espacio-worker-0015`. El catalogador, FlareSolverr y Jellyfin estaban activos en la última comprobación. **No se modificó la tarea de Windows**.
- El publicador Windows pasó `Preflight`, sin reclamar trabajos ni publicar archivos.
- **10/10 smoke de solo lectura** en la API/web, **1042/1042 tests backend**, **18/18 tests frontend** y build Next.js de producción correcta; Ruff, TS y ESLint verificados en sus respectivos hitos. Dos warnings de dependencias externas en pytest.
- La dirección `http://192.168.1.138:3000/tv.html` sigue disponible como versión Samsung anterior. La sección nueva **Espacio** existe en la interfaz principal `/`, **no** en `tv.html`.

## 2. Auditoría de borrado real: avances y límites

- Dos diarios privados de publicación corresponden a **dos hardlinks NTFS** verificados con volumen, identificador del archivo, tamaño, contador de enlaces y huella del manifiesto; también coinciden de forma exclusiva con dos rutas de película consultadas a Jellyfin por ID. Es información de identificación, no una autorización de borrado.
- Existe **una carpeta de película sin diario verificable**: conservarla y excluirla de retiradas automatizadas.
- Dos torrents de ViewTV, asociados a esas publicaciones, estaban **EN USO** en la última consulta GET de qBittorrent, ninguno parado. **No intentar detenerlos ni eliminarlos** sin la política y aprobación del administrador.
- Se probó en un **sandbox temporal Windows independiente** la retirada de un hardlink ficticio: su original permaneció intacto. Ninguna película real se tocó.
- Existe el evaluador puro `worker/retirement_guards.py`, con tests que rechazan torrents ajenos, incompletos, activos, duplicados, ambiguos o fuera de raíz. Su resultado `apto_parcialmente` no es permiso de retirar.
- **Borrados reales = 0. Bytes reales liberados por retirada = 0.** No hay ejecutor de eliminación habilitado ni disparador al marcar «vista».

## 3. Pendiente prioritario para mañana (lunes 23/11/2026)

**Continuar exclusivamente con gestión de espacio antes de iniciar la app Samsung.**

1. Diseñar y probar **autoridad de administrador de biblioteca** separada del PIN de un perfil; requerir aprobación explícita de la película exacta y de las consecuencias sobre otros perfiles y el torrent original.
2. Implementar el **preflight único y coherente** de SQLite ↔ diario del publicador Windows ↔ hardlink NTFS ↔ ruta Jellyfin ↔ torrent qBittorrent, revalidando justo antes de cualquier cambio. No usar nombres de películas para dar propiedad.
3. Controlar lectores/streams y descargas en curso, hardlinks adicionales, raíz de medios, junctions/reparse y carreras con el publicador. Denegar y registrar los casos incompletos.
4. Diseñar la retirada con registro durable, fases auditables, recuperación tras fallo y medición de **bytes físicamente liberados**; retirar archivos originales solo tras verificar propiedad exclusiva y detener torrents propios con autorización específica.
5. Ampliar ensayos en sandbox NTFS. **No probar el ejecutor sobre películas reales** sin esas garantías y la aprobación concreta.
6. Implementar una cuota/evicción real **solo sobre caché creada y poseída por ViewTV**, sin limpiar caché Jellyfin, torrents, metadatos TMDB o ficheros desconocidos.
7. Probar la pantalla «Espacio» con sesión de usuario y decidir integración posterior en app Samsung.

## 4. Tareas futuras, en el orden acordado

1. **Primero:** cerrar de forma segura gestión de espacio, caché y retirada de películas vistas.
2. **Después:** aplicación Samsung Tizen instalable con apariencia profesional tipo Netflix/Prime Video, carátulas a color, mando/foco y reproducción validada en la TV real.
3. **Por último:** «VIEWTV Momentos», feed de clips verticales 9:16 pensado para TV, cruceta arriba/abajo y OK → película exacta, usando solo clips con derechos válidos, filtros de spoilers y permisos por perfil.

La idea de «Momentos» está documentada desde el 22/11/2026; **todavía no se implementa**.

## 5. Puntos de recuperación y comprobaciones al retomar

- Repositorio de trabajo WSL: `/home/viewtv/projects/viewtv-broker-0013-20261119`.
- Revisar rama y ausencia de cambios: `git status --short --branch`; comprobar que PR #2 sigue OPEN/DRAFT. **No cambiar de rama ni fusionar PR.**
- Comprobar salud con consultas sin escritura y preflight del publicador; no usar operaciones `claim`, `sync`, `delete`, `stop`, `remove` como diagnósticos.
- Respaldos previos comprobados:
  - `/home/viewtv/viewtv-backups/gestion-espacio-cache-pre-20261122-224320.tar.gz`, SHA-256 `cd32ed2cf5ffa9041d06e2d4564cec44ce059506e8d9c2760d50b55fd78b8ca8`.
  - SQLite productiva `/home/viewtv/viewtv-backups/api-resultados-predeploy-20261122-225105.db`, SHA-256 `ac0352f867deae7d3336ef6c92cbe33049d1d7de75de56b25da5a80b13d32e30` (respaldo privado, no subir a GitHub).
  - `/home/viewtv/viewtv-backups/retirada-ntfs-compatibilidad-pre-20261122-230050.tar.gz`, SHA-256 `a7956ddf51895883d8448b0a90082ba5c602eebe09e4b3016fcf570fa1890b53`.
  - Documentación antes del cierre: `/home/viewtv/viewtv-backups/cierre-jornada-docs-pre-20261122-231937.tar.gz`, SHA-256 `920baa73ac8f5e48722e915e4c53ccba9098200d3a80a816f2f3607a54fbf576`.
- Informes principales:
  - [Gestión de espacio 0015](AVANCE-GESTION-ESPACIO-CACHE-0015-20261122.md)
  - [Auditoría y bloqueos de retirada 0016](AVANCE-AUDITORIA-RETIRADA-SEGURA-0016-20261122.md)
  - [Idea de clips verticales para la TV](IDEA-FUTURA-MOMENTOS-VERTICALES-TV-20261122.md)
  - [BACKLOG](BACKLOG.md) y [plan](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

**Hecho hoy:** panel Espacio, marcas por perfil, retirada solicitada/cancelable, preflight Windows restaurado, auditoría real NTFS/Jellyfin/qBit, ensayos de sandbox, pruebas, informes y commits.
**Supuesto crítico pendiente:** no se puede afirmar espacio recuperable con tamaño lógico de hardlinks; verificar derechos y titularidad antes de borrar.
**Pendiente mañana:** ejecutor y autorización de retirada real más cuota de caché efectiva. **No iniciar aún la app Samsung.**
