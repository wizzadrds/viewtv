# Backend de VIEWTV

API HTTP de VIEWTV construida con FastAPI y SQLModel. SQLite almacena perfiles, metadatos del catálogo, solicitudes y estado de las descargas. Los archivos multimedia y temporales no se guardan en la base de datos.

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

Los PIN se almacenan mediante Argon2id (Argon2 PasswordHasher). El login devuelve una cookie de sesión JWT `httpOnly`, `SameSite=Strict`, con caducidad configurable.

El endpoint de login limita inicialmente los intentos a 5 por minuto y dirección IP. Este limitador reside en memoria del proceso; no proporciona coordinación entre varias réplicas.

Configura `JWT_SECRET` con al menos 32 caracteres aleatorios. Para desarrollo HTTP local, `AUTH_COOKIE_SECURE=false`; cuando se publique detrás de HTTPS, debe ser `true`. No expongas la API a Internet.

Con Docker, crea perfiles desde la raíz del repositorio:

```bash
docker compose exec api sh -c 'cd /opt/viewtv/backend && python scripts/create_profile.py'
```

El comando solicita el PIN dos veces sin mostrarlo. No lo escribas en argumentos de terminal ni lo guardes en archivos del repositorio.

Rutas principales de autenticación:

- `POST /auth/login`: valida nombre y PIN.
- `GET /auth/me`: devuelve el perfil autenticado.
- `POST /auth/logout`: elimina la cookie de sesión.

## Solicitudes y descargas

`POST /solicitudes` crea una solicitud para el perfil autenticado. Comprueba la existencia del medio, evita solicitudes activas duplicadas y realiza la operación de escritura dentro de una transacción `BEGIN IMMEDIATE`.

El modelo `Descarga` conserva el estado y los datos de seguimiento de una transferencia. Sus estados contemplados incluyen `seleccionada`, `enviada`, `descargando`, `pausada`, `completada` y `fallida`.

La migración `0004` incorpora el modelo y sus restricciones. La existencia del endpoint, del modelo y de los clientes HTTP no significa que el procesamiento completo de solicitudes y transferencias esté integrado: ese trabajo corresponde a entregables posteriores de la fase 2.

## Base de datos y migraciones

Las tablas y modelos incluyen perfiles, medios, solicitudes y descargas. Los metadatos del catálogo son independientes de los archivos de caché.

La cola de solicitudes conserva los campos de lease `locked_by`, `locked_until` y `heartbeat` para permitir la recuperación de trabajos.

Para aplicar migraciones en un entorno preparado:

```bash
alembic upgrade head
```

La creación automática de tablas está limitada al desarrollo y las pruebas; los entornos persistentes deben utilizar Alembic.

## Seguridad

- No subas `.env`, credenciales, PIN, tokens ni claves API.
- No compartas bases de datos locales.
- Mantén los servicios accesibles únicamente desde las redes autorizadas.
- Utiliza exclusivamente fuentes y contenido cuyo uso esté autorizado.
