clean:
	@find . -name "*.pyc" | xargs rm -rf
	@find . -name "*.pyo" | xargs rm -rf
	@find . -name "__pycache__" -type d | xargs rm -rf

test: clean
	@flake8 camomilla
	# @pytest-3 --cov=camomilla -s --cov-report=xml --cov-report=term-missing
	@pytest --cov=camomilla -s --cov-report=xml --cov-report=term-missing

docs: clean
	@npm run docs:publish