# VIEWTV — frontend

Interfaz inicial de VIEWTV con Next.js App Router, React y TypeScript. Idioma español (España), diseño adaptable a TV/móvil y navegación espacial mediante cruceta.

## Requisitos

- Node.js 20.9 o superior y npm.
- API VIEWTV activa en `http://127.0.0.1:8000`.

## Desarrollo en Ubuntu/WSL

Desde la raíz del repositorio:

```bash
cd frontend
npm install
npm run dev
```

Abrir `http://localhost:3000`. El proxy de Next.js reenvía `/api/viewtv/*` a la API, de modo que la cookie HttpOnly permanece en el mismo origen del navegador. Si la API está en otra dirección accesible desde el proceso Next.js, configurar `VIEWTV_API_INTERNAL_URL`.

## Funciones de esta primera iteración

- Descubrimiento de perfiles activos mediante `GET /auth/profiles`; solo expone ID y nombre, nunca hashes PIN.
- Acceso mediante PIN, sesión existente consultada en `/auth/me` y cierre de sesión.
- Catálogo Jellyfin, filtros, búsqueda local y sincronización manual.
- Carátulas y fondos a través del proxy autenticado de VIEWTV.
- Navegación espacial con flechas entre controles y soporte Enter nativo.
- Manifest instalable e icono SVG.
- Ficha informativa de título.

La reproducción desde la PWA, service worker/offline, paginación incremental y pruebas en Fire TV todavía no están implementados. Esta primera iteración carga hasta 50 elementos por consulta, según el límite de la API.
