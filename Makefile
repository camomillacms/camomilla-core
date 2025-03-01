clean:
	@find . -name "*.pyc" | xargs rm -rf
	@find . -name "*.pyo" | xargs rm -rf
	@find . -name "__pycache__" -type d | xargs rm -rf

test: clean
	@flake8 camomilla
	@pytest --cov=camomilla -s --cov-report=xml --cov-report=term-missing

docs: clean
	@NODE_OPTIONS=--openssl-legacy-provider npm run docs:publish