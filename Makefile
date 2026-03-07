.PHONY: help install install-dev test test-cov lint format type-check check clean run build upload upload-test release ci

VERSION := $(shell uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
TAG ?= v$(VERSION)

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install project dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  test         - Run tests"
	@echo "  test-cov     - Run tests with coverage report"
	@echo "  lint         - Run linter (ruff check)"
	@echo "  format       - Format code (ruff format)"
	@echo "  format-check - Check code formatting"
	@echo "  type-check   - Run type checker (pyright)"
	@echo "  check        - Run all checks (lint, format-check, type-check)"
	@echo "  fix          - Fix auto-fixable issues (ruff check --fix)"
	@echo "  clean        - Clean build artifacts and cache files"
	@echo "  run          - Run the CLI (use ARGS='<args>')"
	@echo "  build        - Build package artifacts into dist/"
	@echo "  upload       - Upload built package to PyPI"
	@echo "  upload-test  - Upload built package to TestPyPI"
	@echo "  release      - Run checks/tests, build, tag, and push release"
	@echo "  ci           - Run all CI checks (check + test + build)"

# Installation
install:
	uv sync

install-dev:
	uv sync --group dev

# Testing
test:
	uv run pytest -v

test-cov:
	uv run pytest --cov --cov-report=term-missing

test-cov-html:
	uv run pytest --cov --cov-report=html
	@echo "HTML coverage report: htmlcov/index.html"

# Code quality
lint:
	uv run ruff check privacyforms_pdf tests

format:
	uv run ruff format privacyforms_pdf tests

format-check:
	uv run ruff format --check privacyforms_pdf tests

type-check:
	uv run ty check

check: lint format-check type-check
	@echo "All checks passed!"

fix:
	uv run ruff check --fix privacyforms_pdf tests

# Cleaning
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Run CLI with arguments (e.g., make run ARGS='info samples/FilledForm.pdf')
run:
	uv run pdf-forms $(ARGS)

# Development workflow
dev-setup: install-dev
	@echo "Development environment ready!"
	@echo "Run 'make check' to verify everything is working"

# Build
build:
	uv build
	@echo "Build artifacts created in dist/"

upload: check
	@echo "Uploading to PyPI..."
	uvx twine upload dist/*

upload-test: check
	@echo "Uploading to TestPyPI..."
	uvx twine upload --repository testpypi dist/*

release: check test build
	@git diff-index --quiet HEAD -- || (echo "Working tree is not clean. Commit or stash changes before release." && exit 1)
	@git rev-parse "$(TAG)" >/dev/null 2>&1 && (echo "Tag $(TAG) already exists." && exit 1) || true
	git tag -a "$(TAG)" -m "Release $(TAG)"
	git push origin master
	git push origin "$(TAG)"
	@echo "Release $(TAG) created and pushed."
	@echo "Run 'make upload' to publish to PyPI."

ci: check test build
	@echo "CI checks passed!"
