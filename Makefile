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
	@rm -rf example/test_db.sqlite3

install:
	uv sync --dev

format:
	uv run black .

lint:
	uv run flake8 camomilla

test: clean
	uv run flake8 camomilla
	uv run pytest --cov=camomilla -s --cov-report=xml --cov-report=term-missing

migrations: clean
	@mkdir -p camomilla_migrations
	@touch camomilla_migrations/__init__.py
	uv run python manage.py makemigrations camomilla

migrations-reset:
	@rm -rf camomilla_migrations
	@make migrations

docs-dev: clean
	pnpm run docs:dev

docs-build: clean
	pnpm run docs:build

docs-publish: clean
	pnpm run docs:publish


.PHONY: clean install format lint test migrations migrations-reset docs-dev docs-build docs-publish