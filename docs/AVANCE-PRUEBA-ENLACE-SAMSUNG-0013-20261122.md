# VIEWTV — preflight del enlace Samsung, antes de la prueba física

**Fecha:** 22/11/2026, Europe/Madrid
**Rama:** `viewtv-seguimiento-descargas-0012`. PR #2 debe seguir abierto y en borrador.
**Hito:** Tarea 1, arranque en televisión Samsung. No se inicia la tarea 2.

## Objetivo

Probar primero ViewTV como página accesible por LAN desde Samsung y,
solo después de confirmar uso real, valorar la aplicación web empaquetada
para Tizen. **No se afirma que la televisión funcione porque HTTP dé 200.**

URL de prueba física: `http://192.168.1.138:3000/tv.html`.

La página `tv.html` es un frontend autónomo ES5 con `XMLHttpRequest`,
no depende de la hidratación de React/Next. Usa API same-origin
`/api/viewtv/*`, sin URLs de API hacia `localhost` en el navegador.
La URL raíz `/` continúa sirviendo la aplicación Next y puede
mostrar la pantalla «Iniciando VIEWTV…» en navegadores antiguos.

## Observación read-only del equipo y servidor

- Remote Desktop Commander conectado al Windows/WSL autorizado.
- Worktree: `/home/viewtv/projects/viewtv-broker-0013-20261119`.
  Rama correcta, limpio al empezar esta intervención; HEAD inicial
  `632ae6b`. Otros worktrees y ramas no alterados.
- Contenedores en funcionamiento, sin recreación:
  frontend `viewtv-frontend:samsung-busqueda-0013` (healthy),
  API `viewtv:busqueda-tmdb-api-0013` (healthy),
  worker `viewtv:busqueda-tmdb-worker-0013` (en marcha).
  No se modificó la configuración ni se imprimieron claves.
- `HEAD /tv.html` en IP LAN: **HTTP 200**, `text/html`.
  `GET /tv.html`: cuerpo contiene VIEWTV, script ES5 y
  `var api="/api/viewtv"`. El endpoint sirve la página esperada.
- `GET /api/app-version`: **HTTP 200**.
- `GET /api/viewtv/auth/profiles`: **HTTP 200**, contenido privado
  no mostrado; `GET /api/viewtv/auth/me` sin cookies:
  **HTTP 401** esperado. No se introdujo PIN ni sesión real.
- Validador `scripts/viewtv_tv_samsung_static_validate_0013.py`:
  **SAMSUNG_HTML=OK**, **SAMSUNG_JS_ES5_SINTAXIS=OK**,
  **SIN_REACT_SIN_PROMISE_SIN_FETCH=SI**.
- Smoke de solo lectura `scripts/viewtv_release_smoke_0012_readonly.py`:
  **10/10 PASS**. Comprueba proxy y autenticación protegida;
  no constituye prueba de navegación TV.

## Nuevo test de arranque sin React

`frontend/tests/tv-link-startup.test.mjs` ejecuta el JavaScript real
extraído de `tv.html` con un DOM y XMLHttpRequest simulados, sin red:

1. Si `/auth/me` devuelve 401, ofrece perfiles mediante GET del proxy,
   sin intentar endpoints absolutos ni iniciar sesión.
2. Si falla la carga de perfiles, aparece error y botón de reintento.
3. Si ya existe sesión simulada, abre Explorar y no emite POST ni
   solicitudes de torrents por el mero hecho de navegar.

**3/3 PASS** nuevos; suite completa frontend **18/18 PASS**.
No se usaron perfiles ni credenciales productivas en el test.
El test demuestra comportamiento lógico, no compatibilidad física
con un modelo Samsung determinado.

## Respaldo previo verificado

Ruta:
`/home/viewtv/viewtv-backups/samsung-enlace-verificacion-pre-20261122-220157.tar.gz`

SHA-256:
`8e8d79f343914d5517e4210582f6f1d2a9f89f4373da59777c665ccbd542b5ad`

`tar -tzf` ejecutado y correcto: página Samsung, validador,
smoke, tests previos e informes de arranque y búsqueda.
Sin `.env`, bases de datos ni secretos.

## Qué se hizo, qué se supuso y qué queda

**Hecho:** diagnóstico read-only, test nuevo de arranque de la
página compatible, cobertura de error de perfiles y documentación.
Ningún despliegue, edición de producción, backup SQLite, torrent,
worker, API, Jellyfin o publicador Windows fue necesario.

**Supuesto:** la versión del navegador Samsung del usuario aún
no es conocida; ES5/XHR cubre navegadores más antiguos que
la app Next, pero códecs, cookies, interacción por cruceta y
reproducción deben probarse en el dispositivo.

**Pendiente obligatorio para cerrar tarea 1:** abrir en Samsung
`http://192.168.1.138:3000/tv.html` y comunicar SOLO:
- si aparece «¿Quién está viendo?»;
- si se puede elegir perfil e iniciar sesión (sin compartir PIN);
- si abre Explorar/carátulas y navega con cruceta;
- si Biblioteca reproduce un medio autorizado con imagen/sonido/pausa;
- si falla, qué texto exacto y en qué paso, y modelo/año de la TV.

Con el resultado se decide la siguiente corrección mínima,
y se prueba de nuevo en TV **tras cada despliegue**.
No marcar la tarea 1 cerrada sin esta evidencia.
No tocar `docs/BACKLOG.md` ni empezar mejoras de la tarea 2.

## Reversión

Este hito solo agrega test y documentación: revertir el commit
descriptivo si fuese necesario, sin borrar ficheros `.bak`,
sin `git reset --hard` y sin recrear contenedores.
La instalación productiva sigue en sus imágenes previas.
