clean:
	@find . -name "*.pyc" | xargs rm -rf
	@find . -name "*.pyo" | xargs rm -rf
	@find . -name "__pycache__" -type d | xargs rm -rf

sync:
	uv sync --dev

format:
	uv run black .

lint:
	uv run flake8 camomilla

test: clean
	uv run flake8 camomilla
	uv run pytest --cov=camomilla -s --cov-report=xml --cov-report=term-missing

docs-dev: clean
	@pnpm run docs:dev
docs: clean
	@pnpm run docs:publish

.PHONY: clean sync format lint test docs docs-dev