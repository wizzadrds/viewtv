# VIEWTV — diagnóstico y corrección acotada del arranque en Samsung

**Fecha:** 22/11/2026, Europe/Madrid
**Rama exclusiva:** `viewtv-seguimiento-descargas-0012`
**PR:** #2, mantener OPEN/DRAFT.
**Bloqueo:** pantalla «Iniciando VIEWTV…» que no progresa en el televisor.

## Observación anterior a los cambios

- El portproxy y la regla de Windows ya permiten acceso por la LAN,
  según el propietario; GET/HEAD de la portada desde WSL a
  `http://192.168.1.138:3000/` respondió HTTP 200.
- `/api/app-version` respondió HTTP 200 con `Cache-Control: private, no-store`.
- HEAD contra `/api/viewtv/auth/me` respondió 405 con `Allow: GET`:
  se alcanzó el servidor de API, pero HEAD **no demuestra** que GET funcione.
- El helper del cliente `frontend/lib/api.ts` utiliza solo
  `/api/viewtv/*`, con `credentials: same-origin`. No aparece
  `NEXT_PUBLIC_API_BASE_URL` en frontend/Compose rastreados por Git.
  `VIEWTV_API_INTERNAL_URL` del `next.config.ts` es **solo del servidor**.
- El informe de TV anterior describe manifest PWA, pero no registra
  ningún service worker; no hay registro `serviceWorker` en el
  frontend rastreado. La consulta de versión cada 60 s es asíncrona
  y no espera antes del primer render.
- El HTML inicial contiene «Iniciando VIEWTV…». El estado `loading`
  sale mediante `useEffect` y las rutas de autenticación; si el
  bundle no se ejecuta o React no hidrata, no había caducidad.
- En el código sin modificar ya existían usos de
  `new AbortController()` en arranque, actualizaciones y paneles.
  Según Samsung, Tizen 5.0 (2019) usa Chromium M63 y Tizen 5.5
  (2020), M69. `AbortController` no apareció hasta Chrome 66.
  Esto es una incompatibilidad objetiva para Tizen 5.0, aunque sin
  la consola del TV no se puede afirmar que sea la única causa.
- Otra API detectada fuera de este parche: `form.requestSubmit()`
  (Chrome 76+), relevante al confirmar un PIN por teclado. Debe
  verificarse en una fase siguiente si la primera prueba TV lo exige.

Fuentes:
- Samsung: https://developer.samsung.com/smarttv/develop/specifications/web-engine-specifications.html
- Compatibilidad AbortController: https://caniuse.com/abortcontroller
- Next.js 15 Browserslist y polyfills:
  https://nextjs.org/docs/15/architecture/supported-browsers

## Copia previa obligatoria

`/home/viewtv/viewtv-backups/tv-samsung-arranque-pre-20261122-214904.tar.gz`

SHA-256:
`2e5f6cf64325c5f3666e5097149561f87ebdf0e63d147011776b180f2fb3c6aa`

`tar -tzf`: PASS. Incluye código y configuración de frontend,
los `.bak` existentes, la página `tv.html` que ya estaba sin
seguimiento y los cuatro documentos de referencia. No incluye
archivos `.env` ni bases de datos.

## Corrección preparada, sin ampliar alcance

1. `frontend/package.json`: `browserslist` explícito con
   Chrome 63 como objetivo mínimo para Tizen 5.0; se conservan
   Edge 79, Firefox 67 y Safari 12.
2. `frontend/app/layout.tsx`: script ES5 inline en el `head`,
   anterior a los bundles, con `AbortController` de respaldo para
   navegadores que carecen de la API.
3. El mismo script presenta **exactamente a los 10 s** un aviso
   fuera de React si persiste `.boot-screen`; captura el primer
   error de JavaScript visible para el navegador (si existe)
   y consulta con XHR `GET /api/viewtv/auth/me`.
   HTTP 200/401 demuestra que se llegó al proxy; otros códigos
   se muestran. No imprime PIN, cookie, URL de torrents ni secretos.
4. Los cambios locales preexistentes en
   `frontend/components/viewtv-app.tsx`,
   `frontend/app/globals.css` y la nueva `frontend/public/tv.html`
   aportan un enlace manual y una interfaz de compatibilidad.
   Deben conservarse y validarse, no confundir con la
   aplicación completa de Next. Su función es diagnóstico/acceso
   básico, no prueba automática de búsqueda ni reproducción.
5. `frontend/tests/tv-boot-compat.test.mjs`: pruebas aisladas
   del guardián y del proxy relativo, sin red ni datos reales.

**La ausencia de un error capturado NO demuestra que JavaScript
esté bien**: el panel informa que no se completó la hidratación.

## Validaciones realizadas

- Tests frontend completos: **15/15 PASS**, incluidos **4/4**
  casos nuevos del guardián.
- TypeScript `tsc --noEmit --incremental false`: **PASS**.
- ESLint de layout y test: **PASS**.
- Docker build oficial: **PASS**, imagen local
  `viewtv-frontend:samsung-boot-0013`, release
  `v1-95d86ece07e0bf96b878`. Inspección de HTML prerenderizado
  confirma guardián ES5, enlace `/tv.html` y bundles de Next.
  La imagen se construyó sin recrear servicios productivos.
- **Prueba física Samsung: NO REALIZADA**. El conector llega al
  PC Windows/WSL, no a la pantalla ni consola del televisor.
  Nunca declarar funcional la TV solo por HTTP 200 o contenedor sano.

## Prueba visual exigida para cerrar tarea 1

Tras desplegar **solo frontend** con la revisión preparada,
abrir `http://192.168.1.138:3000` en el navegador Samsung,
recargar y observar el contenido durante al menos 10 segundos:

- Si aparece la elección de perfil, comprobar navegación con
  el mando y acceso autorizado sin comunicar PIN al asistente.
- Si sigue `Iniciando`, transcribir exclusivamente el mensaje
  del diagnóstico: error JavaScript y estado HTTP del proxy.
- Si abre `/tv.html`, probar perfiles, carátulas y mando,
  dejando constancia de que es una interfaz alternativa limitada.
- No seleccionar torrents ni iniciar descargas en este hito.

## Reversión y restricciones

No alterar `backend`, `worker`, SQLite, Jackett,
qBittorrent, Jellyfin, Docker de otros servicios ni
`docs/BACKLOG.md`. No activar descargas.
La imagen anterior `viewtv-frontend:tv-auto-update-0013`
se conserva para la reversión controlada de **solo frontend**.
No borrar ficheros `.bak`. No cerrar ni fusionar PR #2.

**Pendiente:** prueba en Samsung real y, solo según su error,
decidir el siguiente cambio mínimo. Tarea 2 no iniciada aquí.
