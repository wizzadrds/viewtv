.PHONY: ayuda config build up down restart ps logs health \
        backend-install backend-test backend-lint \
        frontend-install frontend-typecheck frontend-lint frontend-build \
        test lint check

PYTHON ?= .venv/bin/python
NPM ?= npm
COMPOSE ?= docker compose

ayuda:
	@echo "VIEWTV - tareas disponibles"
	@echo ""
	@echo "  make config              Validar configuración de Docker Compose"
	@echo "  make build               Construir las imágenes"
	@echo "  make up                  Construir e iniciar los servicios"
	@echo "  make down                Detener los servicios sin borrar volúmenes"
	@echo "  make restart             Reiniciar los servicios"
	@echo "  make ps                  Mostrar estado de los contenedores"
	@echo "  make logs                Seguir los registros de API y worker"
	@echo "  make health              Comprobar el endpoint de salud"
	@echo "  make backend-install     Instalar backend y herramientas de desarrollo"
	@echo "  make backend-test        Ejecutar pruebas del backend"
	@echo "  make backend-lint        Ejecutar Ruff"
	@echo "  make frontend-install    Instalar dependencias del frontend"
	@echo "  make frontend-typecheck  Comprobar tipos de TypeScript"
	@echo "  make frontend-lint       Ejecutar ESLint"
	@echo "  make frontend-build      Construir la PWA"
	@echo "  make test                Ejecutar pruebas del backend"
	@echo "  make lint                Comprobar backend y frontend"
	@echo "  make check               Ejecutar todas las comprobaciones"

config:
	$(COMPOSE) config --quiet

build:
	$(COMPOSE) build

up: config
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f api worker

health:
	curl --fail --show-error http://localhost:$${API_PORT:-8000}/health

backend-install:
	cd backend && $(PYTHON) -m pip install -e ".[dev]"

backend-test:
	cd backend && $(PYTHON) -m pytest -v

backend-lint:
	cd backend && $(PYTHON) -m ruff check app tests scripts

frontend-install:
	cd frontend && $(NPM) ci --no-audit --no-fund

frontend-typecheck:
	cd frontend && $(NPM) run typecheck

frontend-lint:
	cd frontend && $(NPM) run lint

frontend-build:
	cd frontend && $(NPM) run build

test: backend-test

lint: backend-lint frontend-lint

check: backend-test backend-lint frontend-typecheck frontend-lint frontend-build
