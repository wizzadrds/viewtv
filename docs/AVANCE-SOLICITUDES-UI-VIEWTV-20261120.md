# VIEWTV — solicitud y selección de contenido desde la interfaz

**Fecha:** 20-11-2026.
**Rama:** `viewtv-seguimiento-descargas-0012`.
**Objetivo:** completar funciones imprescindibles para poder usar VIEWTV,
según el [plan maestro de salida](PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md).

## Brecha concreta que impedía completar el flujo

El usuario ya puede iniciar sesión, consultar la biblioteca y reproducir
vídeos. Las descargas y el catálogo se refrescan automáticamente. Sin
embargo, **la interfaz solo tenía búsqueda local en la biblioteca y una
pantalla de seguimiento**, no un formulario de solicitud de nuevo contenido
ni una lista para elegir el resultado buscado.

La **API desplegada ya implementaba** y exponía, tras autenticación,
estas cuatro operaciones:

- `POST /solicitudes`: solicita búsqueda por título, película/serie
  y año opcional; comprueba duplicados activos.
- `GET /solicitudes`: lista solo solicitudes del perfil autenticado.
- `GET /solicitudes/{id}/resultados`: devuelve resultados almacenados
  por el worker, únicamente cuando espera selección.
- `POST /solicitudes/{id}/seleccion`: valida el resultado del perfil,
  evita duplicados activos y registra una descarga seleccionada.

No se necesitaron cambios del backend, migraciones ni reconfiguración de
Jackett/qBittorrent para ofrecer la pantalla.

## Solución implementada

- Nuevo `frontend/components/requests-panel.tsx`: formulario manual
  con título obligatorio, tipo (película/serie) y año opcional, lista de
  solicitudes con estados legibles, acceso a resultados, resolución,
  tamaño, fuentes y botón explícito **Seleccionar**. Después enlaza
  a la pestaña existente **Descargas**.
- `frontend/components/viewtv-app.tsx`: nueva navegación
  **«Buscar y pedir»** con protección de sesión y soporte para mando
  mediante `data-spatial`. Biblioteca, Descargas y reproducción
  permanecen disponibles.
- `frontend/app/globals.css`: estilos responsive mínimos para el
  formulario, lista y resultados.
- El panel consulta **GET cada 10 segundos solo con pestaña visible**,
  además de consultar al entrar y al volver a la pestaña. Cancela
  consultas al desmontarse y descarta respuestas fuera de orden.
- Ninguna petición **POST** ocurre por montar o actualizar el panel:
  crear solicitudes y seleccionar resultados requieren la acción
  explícita de la persona autenticada. Se visualizan los errores de
  la API y los estados fallidos sin repetirlos automáticamente.
- Los resultados de una solicitud anterior se limpian al seleccionar
  otra, evitando mostrar opciones antiguas durante una recarga.

La creación de solicitudes por el usuario **sí escribe en SQLite** y
hace que el worker procese su búsqueda; por eso **no se ejecutaron
solicitudes reales durante la verificación**. Tampoco se ha habilitado
el inicio de torrents:
`VIEWTV_ENABLE_DOWNLOAD_START=false`.

## Evidencias de prueba

- API desplegada: se verificaron desde OpenAPI las 4 rutas
  necesarias, con sus métodos HTTP correctos.
- `backend/tests/test_solicitudes.py`: **26 aprobadas**,
  una advertencia conocida de dependencias, exit code 0,
  usando base aislada en memoria.
- Backend completo: **626 aprobadas**, 2 advertencias conocidas,
  sin caché ni bytecode, exit code 0.
- `frontend/tests/requests-panel.test.mjs`: 5 nuevos contratos
  estáticos de navegación, selección, autenticación, temporizadores
  y ausencia de POST automático.
- Junto con el contrato anterior del panel Descargas:
  **9/9 pruebas Node aprobadas** en contenedor sin red.
  Los tests estáticos no sustituyen una prueba interactiva.
- `npm run build` con Next.js 15.5.28:
  **compilación de producción correcta**, lint y TypeScript correctos,
  generación de 5/5 páginas. Una advertencia CSS detectada durante
  el primer build se corrigió antes de construir la imagen final.
- Después del despliegue: **10/10 pruebas de humo correctas**,
  interfaz y proxy HTTP 200, seguridad HTTP 401 para rutas privadas,
  Jellyfin saludable.
- Inventario agregado de SQLite tras desplegar: **2 perfiles**,
  **2 medios**, **1 solicitud fallida anterior**, **0 nuevas
  solicitudes** y **0 descargas**. No se lanzó ningún torrent.
- El contenedor API sigue en Alembic
  `0012_inicio_torrent (head)`, sin modificación de esquema.

## Respaldos realizados

Antes de modificar los tres archivos existentes, se creó
`/home/viewtv/viewtv-backups/solicitudes-ui-pre-20261120-192910.tar.gz`.

SHA-256:
`f5259904d25f52af569b21f4fb7eab8a2d70bb8cc79a18d2f3c493dc5d59a527`

La lista `tar -tzf` verificó exactamente:

- `frontend/components/viewtv-app.tsx`
- `frontend/app/globals.css`
- `docs/PLAN-SALIDA-RAPIDA-VIEWTV-20261120.md`

El componente nuevo, la prueba, el informe y los dos overrides Compose
no tenían versiones anteriores.

Antes de desplegar se creó copia consistente de SQLite desde
contenedor efímero sin red con volumen de origen **solo lectura**:

`/home/viewtv/viewtv-backups/solicitudes-ui-pre-20261120-193414/viewtv-api-0012-before-recreate.db`

SHA-256:
`171dc1d3e73287e0c8fd45a265e8512961818ff416af301e9168b5a983bb2891`

Comprobados: 163840 bytes, revisión 0012, `integrity_check=ok`,
cero errores de `foreign_key_check`. El hash se verificó también
en Ubuntu. No se restauró SQLite ni se realizó una escritura de prueba
sobre los datos reales; el worker existente conserva su sincronización
periódica independiente.

## Imagen, despliegue y reversión

La imagen nueva es `viewtv-frontend:solicitudes-0012`,
ID de Docker:

`sha256:5d812f506e6ab80b8e23f8b602dff3ff8390ce7b2e3b3da67bb7797c795231ba`

Se aplicó **solo el frontend** mediante `docker compose
up --no-deps --no-build --force-recreate -d frontend`, usando
cuatro Compose base existentes y, en orden, estos overrides
versionados:

1. `deploy/compose.catalog-auto-0012.yaml`
2. `deploy/compose.descargas-auto-0012.yaml`
3. `deploy/compose.solicitudes-0012.yaml`

El efectivo conserva:
- API: `viewtv:predeploy-0012-release`
- Worker: `viewtv:catalog-auto-0012`
- Frontend: `viewtv-frontend:solicitudes-0012`

El frontend quedó **healthy** y API/Jellyfin/FlareSolverr siguieron
**healthy**, worker activo. No se reiniciaron esos servicios.

Si fallara la nueva pantalla, usar los mismos overrides y añadir
como **último** `deploy/compose.solicitudes-0012-rollback.yaml`.
Después recrear **solo frontend** y repetir pruebas de humo. El
override de reversión restaura `viewtv-frontend:descargas-auto-0012`
sin cambiar bases de datos, worker, API ni volúmenes.
**Se verificó la configuración de reversión, pero no se ejecutó**
porque el frontend nuevo superó las pruebas.

## Pendiente para completar realmente la función

Todavía **NO** se ha ejecutado una solicitud desde un perfil real,
ni se ha comprobado que una búsqueda Torznab reciente devuelva
resultados correctos, que el usuario seleccione uno y que el estado
aparezca en Descargas. Esas son las próximas pruebas de aceptación,
sin usar credenciales del usuario ni crear solicitudes en su nombre.

Las descargas reales, su seguimiento completo y el organizador 0013
siguen pendientes. No activar qBittorrent ni mover medios sin una
prueba autorizada y reversible.

**Decisión:** funcionalidad de solicitudes y selección implementada,
construida y publicada en la interfaz; **validación real con el
usuario pendiente**. Plan y evidencia quedan bajo control de Git,
PR #2 en borrador y sin fusionar.
