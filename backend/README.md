# Backend de VIEWTV

API HTTP con FastAPI y SQLModel. La base de datos guarda perfiles, metadatos del catálogo y solicitudes; los ficheros multimedia y temporales pertenecen a la caché y nunca se guardan en SQLite.

## Desarrollo local en Ubuntu/WSL2

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
pytest
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Comprobación: `http://localhost:8000/health`.

## Base de datos y migraciones

Las tablas iniciales son `perfil`, `medio` y `solicitud`. Los metadatos del catálogo son independientes de los archivos de caché. La cola conserva los campos de lease `locked_by`, `locked_until` y `heartbeat` para permitir recuperación tras reinicios.

Para aplicar migraciones en un entorno preparado:

```bash
alembic upgrade head
```

La creación automática de tablas está limitada al desarrollo y las pruebas; los despliegues persistentes deben usar Alembic.