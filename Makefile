clean:
	@find . -name "*.pyc" | xargs rm -rf
	@find . -name "*.pyo" | xargs rm -rf
	@find . -name "__pycache__" -type d | xargs rm -rf
	@rm -rf .pytest_cache
	@rm -rf .ruff_cache
	@rm -rf htmlcov
	@rm -rf .coverage*
	@rm -rf coverage.xml
	@rm -rf dist
	@rm -rf django_camomilla_cms.egg-info
	@rm -rf test_db.sqlite3

sync:
	uv sync --dev

format:
	uv run black .

lint:
	uv run flake8 camomilla

test: clean
	uv run flake8 camomilla
	uv run pytest $(if $(DB_BACKEND),--db-backend=$(DB_BACKEND),) --cov=camomilla -s --cov-report=xml --cov-report=term-missing

# Explicit DB targets (useful for CI and local clarity)
test-sqlite: clean
	uv run flake8 camomilla
	uv run pytest --db-backend=sqlite --cov=camomilla -s --cov-report=xml --cov-report=term-missing

test-postgres: clean
	uv run flake8 camomilla
	uv run pytest --db-backend=postgres --cov=camomilla -s --cov-report=xml --cov-report=term-missing

test-mysql: clean
	uv run flake8 camomilla
	uv run pytest --db-backend=mysql --cov=camomilla -s --cov-report=xml --cov-report=term-missing

docs-dev: clean
	@pnpm run docs:dev
docs: clean
	@pnpm run docs:publish

.PHONY: clean sync format lint test test-sqlite test-postgres test-mysql docs docs-dev