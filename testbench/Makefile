# ===========================
# Project Variables
# ===========================
PROJECT_NAME = testbench
PYTHON = python3
PIP = pip
VENV_DIR = .venv
GUNICORN_WORKERS = 4
APP_MODULE = src.main:app
GUNICORN_CONF = gunicorn.conf.py
ALEMBIC = PYTHONPATH=src $(VENV_DIR)/bin/alembic
DOCKER_COMPOSE = docker-compose
DB_URL = postgresql+asyncpg://user:password@localhost:5432/testbench_db
REDIS_URL = redis://localhost:6379
MIGRATION_MESSAGE ?= "update"

# ===========================
# Setup & Installation
# ===========================

.PHONY: install
install: venv
	@$(VENV_DIR)/bin/$(PIP) install -r requirements.txt

.PHONY: venv
venv:
	@$(PYTHON) -m venv $(VENV_DIR)
	@$(VENV_DIR)/bin/$(PIP) install --upgrade pip

.PHONY: activate
activate:
	@echo "Run: source $(VENV_DIR)/bin/activate"

# ===========================
# Database Setup
# ===========================
.PHONY: migrate-current
migrate-current: install
	@$(ALEMBIC) -c alembic.ini current --verbose

.PHONY: migrate-history
migrate-history: install
	@$(ALEMBIC) -c alembic.ini history

.PHONY: migrate-upgrade
migrate-upgrade: install
	@$(ALEMBIC) -c alembic.ini upgrade head

.PHONY: migrate-downgrade
migrate-downgrade: install
	@$(ALEMBIC) -c alembic.ini downgrade -1

.PHONY: makemigrations
makemigrations: install
	@$(ALEMBIC) -c alembic.ini revision --autogenerate -m "$(MIGRATION_MESSAGE)"

.PHONY: migrate-reset
migrate-reset: install
	@$(ALEMBIC) -c alembic.ini downgrade base
	# @$(ALEMBIC) -c alembic.ini upgrade head

# Ensure database initialization on first run
.PHONY: db-init
db-init: install
	@echo "🛠 Initializing database..."
	@$(ALEMBIC) -c alembic.ini upgrade head

# ===========================
# Run Application
# ===========================

.PHONY: run
run: install docker-up
	# @PYTHONPATH=src $(VENV_DIR)/bin/gunicorn -c gunicorn.conf.py -w $(GUNICORN_WORKERS) -k uvicorn.workers.UvicornWorker src.main:app
	@PYTHONPATH=src $(VENV_DIR)/bin/gunicorn -c gunicorn.conf.py -w $(GUNICORN_WORKERS) -k uvicorn.workers.UvicornWorker --log-level debug src.main:app

	# @PYTHONPATH=src $(VENV_DIR)/bin/gunicorn -c $(GUNICORN_CONF) -w $(GUNICORN_WORKERS) -k uvicorn.workers.UvicornWorker --log-level debug  --enable-stdio-inheritance --access-logfile - --error-logfile - $(APP_MODULE)

.PHONY: run-dev
run-dev:
	@$(VENV_DIR)/bin/uvicorn $(APP_MODULE) --host 0.0.0.0 --port 8080 --reload


# ===========================
# Linting & Formatting
# ===========================

.PHONY: lint
lint:
	@$(VENV_DIR)/bin/black src/

.PHONY: format
format:
	@$(VENV_DIR)/bin/isort src/

# ===========================
# Docker Services
# ===========================

.PHONY: docker-up
docker-up:
	@$(DOCKER_COMPOSE) up -d --build

.PHONY: docker-down
docker-down:
	@$(DOCKER_COMPOSE) down -v --rmi all --remove-orphans

.PHONY: docker-logs
docker-logs:
	@$(DOCKER_COMPOSE) logs -f

# ===========================
# Cleanup
# ===========================

.PHONY: clean
clean:
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -delete

.PHONY: clean-db
clean-db:
	@rm -rf migrations/versions/*
	@$(ALEMBIC) -c alembic.ini upgrade head
