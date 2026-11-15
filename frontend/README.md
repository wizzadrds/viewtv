# VIEWTV — frontend

Primera implementación de la interfaz de VIEWTV con Next.js App Router, React y TypeScript. Idioma español (España), diseño adaptable a TV y móvil y navegación espacial mediante cruceta.

## Requisitos

- Node.js 20.9 o superior y npm.
- API VIEWTV accesible desde el proceso de Next.js, inicialmente en `http://127.0.0.1:8000`.

## Desarrollo en Ubuntu/WSL

Desde la raíz del repositorio:

```bash
cd frontend
npm install
npm run dev
```

Abre `http://localhost:3000`.

El proxy de Next.js reenvía `/api/viewtv/*` a la API para mantener las peticiones bajo el mismo origen del navegador y permitir el uso de la cookie `HttpOnly`.

Si la API está en otra dirección accesible desde el proceso Next.js, configura `VIEWTV_API_INTERNAL_URL`.

## Funciones de la primera iteración

- Descubrimiento de perfiles mediante `GET /auth/profiles`, exponiendo ID y nombre, no hashes de PIN.
- Acceso mediante PIN, consulta de sesión existente con `/auth/me` y cierre de sesión.
- Consulta del catálogo Jellyfin.
- Filtros y búsqueda local.
- Sincronización manual del catálogo.
- Carátulas y fondos mediante el proxy autenticado de VIEWTV.
- Navegación espacial con flechas entre controles y soporte de Enter.
- Manifest instalable e icono SVG.
- Ficha informativa de títulos.

## Pendiente de validación o implementación

La existencia del código de esta primera iteración no equivale a una validación completa en navegador o Fire TV.

Continúan pendientes:

- Instalar dependencias y ejecutar la aplicación en el entorno de desarrollo.
- Validar el flujo de navegación y autenticación en navegador.
- Comprobar el comportamiento con mando en Fire TV.
- Integrar la reproducción desde la PWA.
- Implementar service worker y funcionamiento offline.
- Incorporar paginación incremental.

La primera iteración carga hasta 50 elementos por consulta, según el límite de la API.

Consulta el estado general y las prioridades en [`docs/ESTADO.md`](../docs/ESTADO.md).
