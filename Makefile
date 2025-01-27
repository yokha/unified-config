SHELL := /bin/bash

# Detect Python version dynamically
PYTHON := $(shell python3 -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')")
VENV_DIR := venv_$(PYTHON)
ACTIVATE := source "$(VENV_DIR)/bin/activate"

# Packaging on oldest supported python version
PKG_VENV_DIR := venv3.8
PKG_PYTHON := python3.8
PKG_ACTIVATE := source "$(PKG_VENV_DIR)/bin/activate"

# Supported Python versions
PYTHON_VERSIONS := 3.8 3.9 3.10 3.11 3.12

PACKAGE_NAME = unified-config

# PyPI URLs for verification
TEST_PYPI_URL = https://test.pypi.org/pypi/$(PACKAGE_NAME)/json
PROD_PYPI_URL = https://pypi.org/pypi/$(PACKAGE_NAME)/json


.PHONY: lint format unit-test init-cov integration-test integration-cov integration-up integration-down 

all: lint format format-check test cov integration package



# Ensure Poetry is installed
ensure-poetry: setup-venv
	@pip install poetry


# Update and export dependencies
update-requirements: ensure-poetry
	@poetry lock
	# @poetry self add poetry-plugin-export@1.8.0
	@poetry export --without-hashes --output requirements.txt
	@poetry export --without-hashes --with dev --output dev-requirements.txt
	@$(MAKE) clean-venv
	@$(MAKE) setup-venv


# Call integration test Makefile from the root folder
integration-test: setup-venv
	$(ACTIVATE) && $(MAKE) --no-print-directory  -C tests/integration test

integration-cov: setup-venv
	$(ACTIVATE) && $(MAKE) --no-print-directory  -C tests/integration cov	

integration-up:
	$(MAKE) -C tests/integration up

integration-down:
	$(MAKE) -C tests/integration down

integration-logs:
	$(MAKE) -C tests/integration logs


# Target to set up a fresh virtual environment
setup-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		if command -v $(PYTHON) > /dev/null 2>&1; then \
			echo "Creating virtual environment with $(PYTHON)..."; \
			$(PYTHON) -m venv $(VENV_DIR); \
		elif command -v python > /dev/null 2>&1; then \
			echo "Creating virtual environment with default python..."; \
			python -m venv $(VENV_DIR); \
		else \
			echo "Error: Python executable not found!"; \
			exit 1; \
		fi; \
		$(ACTIVATE) && pip install --upgrade pip; \
		if [ -f "requirements.txt" ]; then \
			echo "Installing dependencies from requirements.txt..."; \
			$(ACTIVATE) && pip install -r requirements.txt; \
		fi; \
		if [ -f "dev-requirements.txt" ]; then \
			echo "Installing dev dependencies from dev-requirements.txt..."; \
			$(ACTIVATE) && pip install -r dev-requirements.txt; \
		fi; \
	else \
		echo "Virtual environment already exists."; \
	fi

# Clean up build artifacts and the packaging virtual environment
clean-venv:
	@echo "Cleaning up build artifacts and the virtual environment..."
	rm -rf $(VENV_DIR)
	@echo "Cleanup complete!"


lint: setup-venv
	@$(ACTIVATE) && PYTHONPATH=src pylint --jobs=0 src tests

format: setup-venv
	@$(ACTIVATE) && PYTHONPATH=src  black src/ tests/

format-check: setup-venv
	@$(ACTIVATE) && PYTHONPATH=src black --check src tests

unit-test: setup-venv
	@$(ACTIVATE) && PYTHONPATH=src pytest -s -v  tests/unit

unit-cov: setup-venv
	@$(ACTIVATE) && PYTHONPATH=src pytest -s --cov=src --cov-report=term-missing --cov-report=html:htmlcov tests/unit



build: setup-venv
	poetry lock
	poetry build

# require export TEST_PYPI_TOKEN=your_actual_testpypi_token
release-pypi-test: build
	@echo "Uploading to TestPyPI..."
	@if [ -z "$$TEST_PYPI_TOKEN" ]; then \
		echo "Error: TEST_PYPI_TOKEN is not set"; \
		exit 1; \
	fi
	poetry config repositories.testpypi https://test.pypi.org/legacy/
	poetry config pypi-token.testpypi $$TEST_PYPI_TOKEN
	poetry publish --repository testpypi


verify-pypi-test:
	@echo "Verifying release on TestPyPI..."
	@if ! curl -s $(TEST_PYPI_URL) | grep '"version":' > /dev/null; then \
		echo "Error: Package $(PACKAGE_NAME) not found on TestPyPI!"; \
		exit 1; \
	fi
	@echo "Package $(PACKAGE_NAME) found on TestPyPI!"

test-pypi-install:
	@echo "Creating a test virtual environment..."
	python3 -m venv $(VENV_DIR)
	@echo "Activating virtual environment and installing package from TestPyPI..."
	. $(VENV_DIR)/bin/activate && pip install --index-url https://test.pypi.org/simple/ $(PACKAGE_NAME) && \
	python -c "import unified_config; print('Package installed and working correctly!')" && \
	deactivate
	@echo "TestPyPI package installation and basic test completed!"

test-release: release-pypi-test verify-pypi-test test-pypi-install
	@echo "Test release verified successfully!"


# require export PYPI_TOKEN=your_actual_prod_pypi_token
release-pypi-prod: build
	@echo "Uploading to PyPI..."
	@if [ -z "$$PYPI_TOKEN" ]; then \
		echo "Error: PYPI_TOKEN is not set"; \
		exit 1; \
	fi
	poetry config pypi-token.pypi $$PYPI_TOKEN
	poetry publish
	@echo "Production release completed!"


verify-pypi-prod:
	@echo "Verifying release on PyPI..."
	@if ! curl -s $(PROD_PYPI_URL) | grep '"version":' > /dev/null; then \
		echo "Error: Package $(PACKAGE_NAME) not found on PyPI!"; \
		exit 1; \
	fi
	@echo "Package $(PACKAGE_NAME) found on PyPI!"


test-pypi-prod-install:
	@echo "Creating a production test virtual environment..."
	python3 -m venv $(VENV_DIR_PROD)
	@echo "Activating virtual environment and installing package from PyPI..."
	. $(VENV_DIR_PROD)/bin/activate && pip install $(PACKAGE_NAME) && \
	python -c "import unified_config; print('Production package installed and working correctly!')" && \
	deactivate
	@echo "PyPI package installation and basic test completed!"


prod-release: release-pypi-prod verify-pypi-prod test-pypi-prod-install
	@echo "Production release verified successfully!"
