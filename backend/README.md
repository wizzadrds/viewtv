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
ruff check app tests
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Comprobación: `http://localhost:8000/health`.

## Autenticación

Los PIN se guardan con Argon2id (Argon2 PasswordHasher). El login devuelve una cookie de sesión JWT `httpOnly`, `SameSite=Strict`, con caducidad configurable. El endpoint de login limita los intentos a 5 por minuto y dirección IP; este limitador inicial vive en memoria del proceso y se deberá sustituir por uno compartido si se ejecutan varias réplicas.

Configura `JWT_SECRET` con al menos 32 caracteres aleatorios. Para desarrollo HTTP local, `AUTH_COOKIE_SECURE=false`; cuando se publique detrás de HTTPS, debe ser `true`. No expongas la API a Internet.

Con Docker, crea los perfiles desde la raíz del repositorio:

```bash
docker compose exec api sh -c 'cd /opt/viewtv/backend && python scripts/create_profile.py'
```

El comando solicita el PIN dos veces sin mostrarlo. No lo escribas en argumentos de terminal ni lo guardes en archivos del repositorio.

Rutas:
- `POST /auth/login`: valida nombre y PIN.
- `GET /auth/me`: devuelve el perfil autenticado.
- `POST /auth/logout`: elimina la cookie de sesión.

## Base de datos y migraciones

Las tablas iniciales son `perfil`, `medio` y `solicitud`. Los metadatos del catálogo son independientes de los archivos de caché. La cola conserva los campos de lease `locked_by`, `locked_until` y `heartbeat` para permitir recuperación tras reinicios.

Para aplicar migraciones en un entorno preparado:

```bash
alembic upgrade head
```

La creación automática de tablas está limitada al desarrollo y las pruebas; los despliegues persistentes deben usar Alembic.
