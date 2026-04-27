.PHONY: test test-integration test-errors test-coverage setup-db docker-up docker-down docker-reset clean help

PYTEST_ARGS?=tests/integration/spatial/
PYTHON=python
PIP=pip
POSTGRES_HOST?=localhost
POSTGRES_PORT?=5432

help:
	@echo "Testes de Integracao Espaciais - Comandos Disponiveis"
	@echo ""
	@echo "setup         - Instalar dependências de teste"
	@echo "docker-up    - Iniciar banco de teste (PostGIS)"
	@echo "docker-down - Parar banco de teste"
	@echo "docker-reset - Recriar banco de teste"
	@echo "test        - Executar testes espaciais"
	@echo "test-errors - Executar testes de erro"
	@echo "test-coverage - Executar com coverage"
	@echo "clean       - Limpar cache"
	@echo ""

setup:
	$(PIP) install pytest pytest-asyncio asyncpg geoalchemy2 sqlalchemy

docker-up:
	docker-compose -f docker-compose.test.yml up -d

docker-down:
	docker-compose -f docker-compose.test.yml down

docker-reset: docker-down docker-up

test: test-integration

test-integration:
	$(PYTHON) -m pytest $(PYTEST_ARGS) -v

test-errors:
	$(PYTHON) -m pytest tests/integration/spatial/test_error_scenarios.py -v

test-coverage:
	$(PYTHON) -m pytest $(PYTEST_ARGS) --cov=. --cov-report=html --cov-report=term

test-quick:
	$(PYTHON) -m pytest $(PYTEST_ARGS) -x -q

test-parallel:
	$(PYTHON) -m pytest $(PYTEST_ARGS) -n auto

clean:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete