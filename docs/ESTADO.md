# Estado del proyecto VIEWTV

Este documento describe lo que existe en el repositorio remoto `main` en el momento del inventario. Se ha revisado el árbol completo de archivos versionados y el contenido de los documentos de referencia.

> **Límite del inventario:** este inventario solo puede confirmar lo que está subido a GitHub. El contexto menciona trabajo local todavía no subido; ese contenido no aparece en el árbol remoto y no es posible describirlo ni verificarlo desde aquí.

## Resumen

El repositorio contiene el andamiaje documental y los archivos de configuración iniciales. Todavía no hay implementación ejecutable: no aparecen código de backend, frontend o worker, configuración de contenedores, migraciones ni pruebas.

La fase 1 sigue abierta. No se considera que el proyecto esté listo para ejecutar.

## Árbol actual

```text
viewtv/
├── .env.example
├── .gitignore
├── README.md
├── backend/
│   └── README.md
├── docs/
│   ├── CONTEXTO.md
│   └── arquitectura.md
├── frontend/
│   └── README.md
└── worker/
    └── README.md
```

## Inventario archivo por archivo

| Archivo | Para qué sirve | Estado |
| --- | --- | --- |
| `.env.example` | Muestra los nombres de los ajustes necesarios para la aplicación, con valores de ejemplo y sin credenciales reales. | Inicial; todavía no hay servicios que consuman estos ajustes. |
| `.gitignore` | Evita subir secretos, entornos virtuales, dependencias, datos locales, bases de datos y cachés. | Presente; revisar si aparecen nuevas carpetas al implementar servicios. |
| `README.md` | Explica qué pretende ser VIEWTV, su arquitectura, el entorno de desarrollo, la seguridad y las fases. | Documentación inicial; advierte correctamente de que el repositorio aún no funciona como instalación. |
| `backend/README.md` | Describe las responsabilidades previstas de la API y sus tecnologías. | Solo documentación; no hay implementación del backend. |
| `docs/CONTEXTO.md` | Documento principal de traspaso: propósito, decisiones cerradas, reglas, estado y próximos trabajos. | Referencia vigente para ejecutar las tareas. |
| `docs/arquitectura.md` | Resume los límites entre interfaz, API, base de datos, worker e integraciones, además de persistencia, cola y seguridad. | Arquitectura inicial; todavía faltan detalles y la sección de fuentes indicada en el contexto. |
| `frontend/README.md` | Describe la PWA prevista y sus requisitos para televisión y mando a distancia. | Solo documentación; no hay aplicación frontend. |
| `worker/README.md` | Describe el proceso independiente y la cola persistente que deberá procesar. | Solo documentación; no hay worker implementado. |

## Qué está hecho

- Existe una descripción del producto y de sus límites.
- Las decisiones principales de arquitectura están recogidas en `docs/CONTEXTO.md`.
- Se han creado los directorios de los tres componentes y un README para cada uno.
- Hay una plantilla de variables de entorno sin secretos reales.
- El archivo de exclusiones contempla los artefactos habituales de Python, Node y los datos locales.
- La documentación inicial separa expresamente la base de datos persistente de la caché multimedia.

## Qué falta

Según el alcance de la fase 1 y las fases posteriores:

- Backend ejecutable con FastAPI y SQLModel.
- Modelos de datos y primera migración de Alembic.
- Base SQLite persistente y configuración real de volúmenes.
- Worker independiente y reclamación transaccional de trabajos mediante lease.
- Frontend Next.js y estructura PWA.
- Compose para levantar los servicios.
- Pruebas automatizadas y configuración de Ruff y pytest en CI.
- Makefile con las tareas de desarrollo y verificación.
- Licencia MIT, pendiente de incorporar según el contexto.
- Completar en `docs/arquitectura.md` la sección de fuentes.
- Resolver la orientación de las portadas mediante el ADR pendiente.

## Qué sobra o conviene revisar

- No se ha identificado ningún archivo que sobre y deba borrarse.
- Los README de backend, frontend y worker son marcadores documentales, no implementaciones. Deben conservarse mientras sirvan para explicar el propósito de cada componente.
- No se debe confundir la presencia de `.env.example` con una configuración ejecutable.
- No se puede confirmar ni descartar trabajo local sin subir: no forma parte del árbol remoto revisado.

## Estado de la fase

**Fase 1 abierta.** Este inventario no cierra la fase ni acredita criterios de aceptación. No se han ejecutado servicios ni pruebas porque todavía no existe la implementación correspondiente.

Siguiente punto de esta tarea: registrar las alternativas de orientación de portadas en el ADR y esperar la elección del propietario antes de aplicar una decisión.
