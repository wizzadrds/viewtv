# VIEWTV — Estado real del proyecto

> **AVISO (19-11-2026):** este inventario refleja la revisión histórica del 18-11-2026 y sus cifras de pruebas ya no son actuales. Para el despliegue real `0012`, los respaldos y el estado pendiente, consultar [DESPLIEGUE-0012.md](DESPLIEGUE-0012.md). Última suite: **347 pruebas aprobadas**.

**Fecha de revisión:** 18 de noviembre de 2026
**Rama local:** `inventario-trabajo-local`
**Commit local:** `482071b`

> Inventario generado desde la carpeta local de Ubuntu/WSL.
> La presencia de un archivo no significa que su
> funcionamiento completo esté validado.
> No describe la rama main.

## Resumen

- API FastAPI, SQLite, autenticación y perfiles implementados.
- Catálogo Jellyfin y proxy de imágenes validados con un medio real.
- Backend de reproducción Direct Play implementado, pendiente
  de integración y validación real de respuestas HTTP 206.
- PWA Next.js implementada inicialmente, sin validación completa
  en navegador ni Fire TV.
- Solicitudes, búsqueda Torznab, selección manual y worker
  de descargas presentes en el código local.
- Integración qBittorrent probada parcialmente; no se ha
  completado una descarga real de extremo a extremo.
- Jackett instalado en Windows y FlareSolverr en Docker.
- Las pruebas locales del backend devolvieron 129 correctas
  y 2 advertencias el 18/11/2026.

## Estado por fases

| Fase | Estado | Pendiente principal |
| --- | --- | --- |
| 1. Base | Muy avanzada | Cierre formal y verificaciones restantes |
| 2. Catálogo Jellyfin | Validado parcialmente | Revisión funcional completa |
| 3. Solicitudes y reproducción | Parcial | Descarga integral y Direct Play real |
| 4. Caché y cuota | Pendiente de cierre | Ciclo de vida, expulsión y pruebas |
| 5. Asistente conversacional | Pendiente | Implementación y pruebas |
| 6. PWA y televisión | Parcial | Validación navegador, mando y Fire TV |

## Infraestructura comprobada

- Docker Compose validado mediante `docker compose config --quiet`.
- API funcionando con estado `healthy`.
- Worker arrancado.
- FlareSolverr 3.5.2 en Docker, `healthy`, puerto local 8191.
- Jackett nativo en Windows, puerto 9117.
- Jackett tiene configurada la URL local de FlareSolverr.
- FlareSolverr devolvió HTTP 200 al navegar a Wikipedia.
- No se ha demostrado aún resolución efectiva de Cloudflare
  desde un indexador Jackett.
- MejorTorrent no se pudo añadir por fallo durante TLS.
- La incidencia y sus registros están documentados
  en `docs/plan-operativo.md`.

## Árbol de componentes

```text
viewtv/
├── backend/ (43 archivos inventariados)
├── worker/ (5 archivos inventariados)
├── frontend/ (12 archivos inventariados)
├── docs/ (10 archivos inventariados)
├── scripts/ (2 archivos inventariados)
├── .github/ (1 archivos inventariados)
├── compose.yaml
├── .env.example
├── Makefile
└── README.md
```

## Inventario archivo por archivo

| Archivo | Función | Estado en Git |
| --- | --- | --- |
| `.github/workflows/backend-ci.yml` | Automatización GitHub | Versionado |
| `README.md` | Configuración del proyecto | Versionado |
| `backend/README.md` | Componente del backend | Versionado |
| `backend/app/__init__.py` | Componente del backend | Versionado |
| `backend/app/auth.py` | Componente del backend | Versionado |
| `backend/app/config.py` | Configuración del backend | Versionado |
| `backend/app/database.py` | Componente del backend | Versionado |
| `backend/app/jackett.py` | Componente del backend | Versionado |
| `backend/app/jellyfin.py` | Integración de catálogo Jellyfin | Versionado |
| `backend/app/jellyfin_playback.py` | Negociación y proxy de reproducción | Versionado |
| `backend/app/main.py` | Punto de entrada de la API | Versionado |
| `backend/app/metadatos_resultado.py` | Metadatos de resultados | Nuevo local; sin seguimiento |
| `backend/app/models.py` | Modelos de datos | Modificado localmente |
| `backend/app/qbittorrent.py` | Cliente de qBittorrent | Modificado localmente |
| `backend/app/queue.py` | Componente del backend | Modificado localmente |
| `backend/app/solicitudes.py` | API de solicitudes y selección | Modificado localmente |
| `backend/app/tmdb.py` | Componente del backend | Versionado |
| `backend/migrations/env.py` | Componente del backend | Versionado |
| `backend/migrations/versions/0001_initial.py` | Migración de base de datos | Versionado |
| `backend/migrations/versions/0002_medio_disponible_en_jellyfin.py` | Migración de base de datos | Versionado |
| `backend/migrations/versions/0003_metadatos_tmdb.py` | Migración de base de datos | Versionado |
| `backend/migrations/versions/0004_descarga.py` | Migración de base de datos | Versionado |
| `backend/migrations/versions/0005_resultados_busqueda.py` | Migración de base de datos | Nuevo local; sin seguimiento |
| `backend/migrations/versions/0006_resultado_descarga.py` | Migración de base de datos | Nuevo local; sin seguimiento |
| `backend/migrations/versions/0007_leases_descarga.py` | Migración de base de datos | Nuevo local; sin seguimiento |
| `backend/migrations/versions/0008_solicitud_jellyfin_nullable.py` | Migración de base de datos | Nuevo local; sin seguimiento |
| `backend/pyproject.toml` | Componente del backend | Modificado localmente |
| `backend/scripts/__init__.py` | Componente del backend | Versionado |
| `backend/scripts/backup_db.py` | Componente del backend | Versionado |
| `backend/scripts/create_profile.py` | Componente del backend | Versionado |
| `backend/tests/test_auth.py` | Prueba automatizada | Versionado |
| `backend/tests/test_backup.py` | Prueba automatizada | Versionado |
| `backend/tests/test_integrations_config.py` | Prueba automatizada | Versionado |
| `backend/tests/test_jackett.py` | Prueba automatizada | Versionado |
| `backend/tests/test_jellyfin.py` | Prueba automatizada | Versionado |
| `backend/tests/test_jellyfin_catalog.py` | Prueba automatizada | Versionado |
| `backend/tests/test_jellyfin_images.py` | Prueba automatizada | Versionado |
| `backend/tests/test_jellyfin_playback.py` | Prueba automatizada | Versionado |
| `backend/tests/test_metadatos_resultado.py` | Prueba automatizada | Nuevo local; sin seguimiento |
| `backend/tests/test_models.py` | Prueba automatizada | Modificado localmente |
| `backend/tests/test_qbittorrent.py` | Prueba automatizada | Modificado localmente |
| `backend/tests/test_queue.py` | Prueba automatizada | Modificado localmente |
| `backend/tests/test_solicitudes.py` | Prueba automatizada | Modificado localmente |
| `backend/tests/test_worker_download_processor.py` | Prueba automatizada | Nuevo local; sin seguimiento |
| `backend/tests/test_worker_processor.py` | Prueba automatizada | Nuevo local; sin seguimiento |
| `compose.yaml` | Servicios y almacenamiento Docker | Modificado localmente |
| `docs/CONTEXTO.md` | Documentación | Versionado |
| `docs/ESTADO.md` | Documentación | Versionado |
| `docs/FASE-2.md` | Documentación | Versionado |
| `docs/REVISION-IMPLEMENTACION.md` | Documentación | Versionado |
| `docs/adr/0001-orientacion-de-portadas.md` | Documentación | Versionado |
| `docs/arquitectura.md` | Documentación | Modificado localmente |
| `docs/backup-operativo.md` | Documentación | Versionado |
| `docs/especificacion-y-estado.md` | Documentación | Versionado |
| `docs/plan-operativo.md` | Documentación | Modificado localmente |
| `docs/reproduccion-jellyfin.md` | Documentación | Versionado |
| `frontend/README.md` | Interfaz web/PWA | Versionado |
| `frontend/app/globals.css` | Interfaz web/PWA | Versionado |
| `frontend/app/layout.tsx` | Interfaz web/PWA | Versionado |
| `frontend/app/manifest.ts` | Interfaz web/PWA | Versionado |
| `frontend/app/page.tsx` | Interfaz web/PWA | Versionado |
| `frontend/components/viewtv-app.tsx` | Interfaz web/PWA | Versionado |
| `frontend/lib/api.ts` | Interfaz web/PWA | Versionado |
| `frontend/next-env.d.ts` | Interfaz web/PWA | Versionado |
| `frontend/next.config.ts` | Interfaz web/PWA | Versionado |
| `frontend/package-lock.json` | Interfaz web/PWA | Versionado |
| `frontend/package.json` | Dependencias y comandos de la PWA | Versionado |
| `frontend/tsconfig.json` | Interfaz web/PWA | Versionado |
| `scripts/backup-daily.ps1` | Script operativo | Versionado |
| `scripts/backup-daily.sh` | Script operativo | Versionado |
| `worker/README.md` | Componente del worker | Modificado localmente |
| `worker/download_processor.py` | Procesamiento de descargas | Nuevo local; sin seguimiento |
| `worker/main.py` | Punto de entrada del worker | Modificado localmente |
| `worker/processor.py` | Procesamiento de solicitudes | Nuevo local; sin seguimiento |
| `worker/tmdb_enrichment.py` | Componente del worker | Versionado |

## Pendientes prioritarios

1. Proteger y revisar los cambios locales antes de subirlos.
2. Verificar el adaptador Torznab y el worker en el despliegue real.
3. Validar una transferencia autorizada completa con qBittorrent.
4. Integrar y probar Direct Play con HTTP Range y respuesta 206.
5. Validar la PWA en navegador y en Fire TV.
6. Completar la gestión de caché, cuota y recuperación de tareas.
7. Completar el asistente conversacional y las pruebas finales.
8. Mantener la documentación actualizada después de cada avance.

## Límites de esta revisión

- Los archivos nuevos locales no están necesariamente
  disponibles en GitHub.
- El inventario registra existencia y estado de Git,
  no certifica el comportamiento individual de cada archivo.
- No se ha ejecutado aquí una reproducción real ni una descarga.
- No se ha realizado un commit ni un push.
- No se ha cambiado de rama.
