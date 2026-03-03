.PHONY: help install install-dev test test-cov lint format clean docker-build docker-run docs

# Default target
help:
	@echo "Available targets:"
	@echo "  install       - Install production dependencies"
	@echo "  install-dev   - Install development dependencies"
	@echo "  test          - Run tests"
	@echo "  test-cov      - Run tests with coverage"
	@echo "  lint          - Run linters (flake8, mypy)"
	@echo "  format        - Format code (black, isort)"
	@echo "  format-check  - Check code formatting"
	@echo "  clean         - Clean build artifacts"
	@echo "  build         - Build package"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run Docker container"
	@echo "  webui         - Start web UI"
	@echo "  cli           - Run CLI (use ARGS='...' to pass arguments)"
	@echo "  docs          - Build documentation"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pip install -r requirements-dev.txt

install-all:
	pip install -e ".[all,dev]"

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

test-integration:
	pytest tests/ -v -m integration

test-fast:
	pytest tests/ -v -m "not slow and not integration"

# Linting and formatting
lint:
	flake8 src/ tests/ --max-line-length=100 --extend-ignore=E203,W503
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/ generate_audiobook.py webui.py
	isort src/ tests/ generate_audiobook.py webui.py

format-check:
	black --check src/ tests/ generate_audiobook.py webui.py
	isort --check-only src/ tests/ generate_audiobook.py webui.py

# Cleaning
clean:
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# Building
build:
	python -m build

# Docker
docker-build:
	docker build -t novel-audiobook-generator:latest .

docker-run:
	docker run -p 7860:7860 -v $(PWD)/output:/app/output novel-audiobook-generator:latest

docker-run-cli:
	docker run -it --rm -v $(PWD)/output:/app/output -v $(PWD)/samples:/app/samples novel-audiobook-generator:latest python generate_audiobook.py $(ARGS)

# Running
webui:
	python webui.py

cli:
	python generate_audiobook.py $(ARGS)

# Documentation
docs:
	cd docs && make html

docs-serve:
	cd docs/_build/html && python -m http.server 8000

# Setup
setup-precommit:
	pre-commit install

# Release
version-patch:
	bump2version patch

version-minor:
	bump2version minor

version-major:
	bump2version major
