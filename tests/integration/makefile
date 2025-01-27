# DC = docker-compose -f tests/integration/docker-compose.yml
DC = docker-compose
PYTHON = python

up:
	$(DC) up -d --build

down:
	$(DC) down --volumes --remove-orphans

logs:
	$(DC) logs -f

test: up
	sleep 2  # Give services time to initialize
	# PYTHONPATH=src pytest -v --disable-warnings test_*.py
	# -o log_cli=true --log-cli-level=DEBUG
	PYTHONPATH=../../src pytest -v test_*.py
	$(MAKE) down

cov: up
	sleep 2  # Give services time to initialize
	# PYTHONPATH=src pytest -v --disable-warnings test_*.py
	# -o log_cli=true --log-cli-level=DEBUG
	PYTHONPATH=../../src pytest -v --cov=../../src --cov-report=term-missing test_*.py
	$(MAKE) down
