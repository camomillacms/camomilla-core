clean:
	@find . -name "*.pyc" | xargs rm -rf
	@find . -name "*.pyo" | xargs rm -rf
	@find . -name "__pycache__" -type d | xargs rm -rf

format:
	@black .

test: clean
	@flake8 camomilla
	@pytest --cov=camomilla -s --cov-report=xml --cov-report=term-missing

docs-dev: clean
	@pnpm run docs:dev
docs: clean
	@pnpm run docs:publish