# VIEWTV — Previsualización aislada de API y frontend 0012

> **Nota de continuidad (19-11-2026):** la DEMO de `3001` continúa separada; posteriormente se desplegó la página **real** en `http://127.0.0.1:3000`. El estado de producción `0011` indicado abajo corresponde al instante anterior al despliegue. Referencia actual: [DESPLIEGUE-0012.md](DESPLIEGUE-0012.md).

Fecha: 19-11-2026. SOLO DESARROLLO, NO PRODUCCIÓN.

## Acceso visual

- URL en el equipo Windows: http://127.0.0.1:3001
- Perfil ficticio: **DEMO VIEWTV**
- PIN ficticio: **2468**
- Pestaña a revisar: **Descargas**; contiene cinco registros totalmente ficticios.

## Aislamiento de producción

- API de demo: contenedor viewtv-preview-0012-api, imagen viewtv:preview-0012-ui.
- PWA demo: contenedor viewtv-preview-0012-pwa, imagen node:22-bookworm-slim, Next.js en modo desarrollo.
- Red propia: viewtv-preview-0012-net. Solo puerto de la PWA expuesto en loopback 127.0.0.1:3001.
- Base SQLite nueva desde cero, migrada de Alembic 0001 a 0012: /home/viewtv/viewtv-previews/0012/preview.db.
- Datos de demostración: /home/viewtv/viewtv-previews/0012/seed_demo.py.
- No se monta el volumen viewtv_viewtv_data ni se usan perfiles o copias de producción.
- Cookie independiente viewtv_preview_session, separada de la real viewtv_session.
- JWT y PIN son solo de demo, nunca para producción.
- No se ha levantado un worker, ni hay claves Jellyfin, qBittorrent, Jackett o TMDB configuradas.
- Producción sigue con API/worker predeploy-0011, SQLite 0011 y sus flags existentes.

## Pruebas confirmadas

- Imagen de API de preview construida desde la última versión de desarrollo.
- Migración Alembic sobre SQLite nueva: exit code 0.
- Backend: 313 pruebas aprobadas (suite anterior).
- TypeScript, ESLint y build Next.js 15.5.28: correctos.
- Prueba HTTP de interfaz, perfiles, rechazo 401 sin sesión, login con cookie HttpOnly, GET de 5 descargas y logout: aprobada.
- Repetir chequeo HTTP local: python3 /home/viewtv/viewtv-previews/0012/check_preview.py

## Comandos de consulta

docker ps --filter name=viewtv-preview
docker logs --tail 30 viewtv-preview-0012-api
docker logs --tail 30 viewtv-preview-0012-pwa

## Detener después de la revisión visual

Únicamente tras la aprobación del usuario, detener SOLO las pruebas:

docker stop viewtv-preview-0012-pwa viewtv-preview-0012-api

El comando stop no borra la base ficticia ni archivos. No usar docker compose down ni eliminar volúmenes.

## Comprobaciones visuales a realizar

1. Login DEMO VIEWTV con PIN 2468 y logout.
2. Pestañas Biblioteca / Descargas y foco mediante teclado o mando.
3. Revisión necesaria, progreso de transferencia y verificación.
4. Actualizar, diseño responsive y contraste en TV y móvil.
5. Mensajes de error sin hash, rutas internas ni botones de inicio de torrent.

Esta demo NO valida reproduccion Jellyfin, descargas reales, organizador ni migración de la base real.
