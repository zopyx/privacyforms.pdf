# AGENTS.md - Project Context for AI Agents

## Project Overview

**privacyforms-pdf** is a Python wrapper library for [pdfcpu](https://pdfcpu.io/) that extracts and manipulates PDF form data.

- **Author**: Andreas Jung <info@zopyx.com>
- **Python Version**: 3.14+
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **License**: (Add your license)

## Architecture

```
privacyforms_pdf/
├── __init__.py          # Public API exports
├── extractor.py         # PDFFormExtractor class - core functionality
└── cli.py               # Click-based command line interface
```

### Core Classes

- **PDFFormExtractor**: Main class for extracting PDF form data
  - Wraps `pdfcpu` command-line tool
  - Handles all PDF form field types (textfield, datefield, checkbox, radiobuttongroup, etc.)
  - Provides methods: `extract()`, `list_fields()`, `get_field_value()`, `has_form()`

- **PDFFormData**: Dataclass representing extracted form data
- **FormField**: Dataclass representing individual form fields

### Exceptions

- `PDFCPUError`: Base exception
- `PDFCPUNotFoundError`: pdfcpu not installed
- `PDFCPUExecutionError`: pdfcpu command failed
- `PDFFormNotFoundError`: PDF has no form

## Tech Stack

| Category | Tool | Command |
|----------|------|---------|
| Package Manager | uv | `uv sync`, `uv add <pkg>` |
| Linter/Formatter | Ruff | `uv run ruff check .`, `uv run ruff format .` |
| Type Checker | ty | `uv run ty check` |
| Testing | pytest + pytest-cov | `uv run pytest` |
| CLI Framework | Click | Defined in `cli.py` |
| Data Validation | Pydantic | For future form filling features |

## Development Workflow

### Setup

```bash
# Install dependencies
uv sync --group dev

# Verify setup
make check          # Run all quality checks
make test           # Run tests
```

### Making Changes

1. **Code**: Edit source files in `privacyforms_pdf/`
2. **Test**: Add/update tests in `tests/`
3. **Check**: Run `make check` (lint + format-check + type-check)
4. **Test**: Run `make test-cov` (ensure >90% coverage)

### Quality Standards

- **Typing**: All code must have complete type hints (Pyright strict mode)
- **Linting**: Ruff with line length 100, Python 3.14 target
- **Testing**: Minimum 90% coverage required
- **Docstrings**: Google-style docstrings for all public APIs

### Makefile Commands

```bash
make help           # Show all available commands
make install-dev    # Install dev dependencies
make test           # Run tests
make test-cov       # Run tests with coverage
make lint           # Run ruff linter
make format         # Format code with ruff
make type-check     # Run ty type checker
make check          # Run all checks (lint + format + type-check)
make fix            # Auto-fix linting issues
make clean          # Clean cache files
make build          # Build package into dist/
make upload         # Upload to PyPI
make upload-test    # Upload to TestPyPI
make ci-build       # Build package for CI
```

## Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py         # pytest fixtures (sample PDF path)
├── test_extractor.py   # Tests for PDFFormExtractor
└── test_cli.py         # Tests for CLI commands
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_extractor.py -v

# Run specific test
uv run pytest tests/test_extractor.py::TestPDFFormExtractorInitialization -v
```

### Mocking Strategy

Tests use `unittest.mock.patch` to mock:
- `subprocess.run` for pdfcpu command execution
- `PDFFormExtractor._find_pdfcpu` to avoid requiring pdfcpu in tests
- File system operations where appropriate

## CI/CD

### GitHub Actions Workflows

| Workflow | File | Trigger |
|----------|------|---------|
| CI | `.github/workflows/ci.yml` | Push/PR to main/master |

### CI Jobs

1. **Lint & Format**: Ruff checks
2. **Type Check**: ty strict mode
3. **Test**: Multi-platform (Ubuntu, macOS) with Python 3.13, 3.13t, 3.14, 3.14t

### Release Process

Manual release process (CI/CD build and publish disabled):

```bash
# 1. Build package
make build

# 2. Upload to PyPI
make upload

# Or upload to TestPyPI first
make upload-test
```

Or use the combined release target (build + tag + push):
```bash
make release  # Creates git tag and pushes
make upload   # Then upload to PyPI separately
```

## Code Conventions

### Imports

```python
from __future__ import annotations

# Standard library (TYPE_CHECKING block for heavy imports)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# Third-party
import click

# Local
from .extractor import PDFFormExtractor
```

### Function Signatures

```python
def extract(self, pdf_path: str | Path) -> PDFFormData:
    """Extract form data from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        PDFFormData containing all form information.

    Raises:
        FileNotFoundError: If the PDF file does not exist.
        PDFFormNotFoundError: If the PDF does not contain a form.
    """
```

### Error Handling

```python
try:
    result = self._run_command([...])
except PDFCPUExecutionError as e:
    # Handle specific error
    raise click.ClickException(f"Failed: {e.stderr}") from e
```

## External Dependencies

### Required System Binary

- **pdfcpu**: Must be installed on the system
  - macOS: `brew install pdfcpu`
  - Linux: Download from GitHub releases
  - Windows: `choco install pdfcpu`

### Python Dependencies

See `pyproject.toml`:
- `click` - CLI framework
- `pydantic` - Data validation (for future features)

## Common Tasks

### Add a New CLI Command

1. Add function in `cli.py` with `@main.command()` decorator
2. Use Click's argument/option decorators
3. Handle errors with `click.ClickException`
4. Add tests in `tests/test_cli.py`

### Add a New Extractor Method

1. Add method to `PDFFormExtractor` in `extractor.py`
2. Use `_run_command()` for pdfcpu calls
3. Handle errors appropriately
4. Add corresponding tests in `tests/test_extractor.py`
5. Update `__init__.py` if public API

### Update Dependencies

```bash
# Add production dependency
uv add <package>

# Add development dependency
uv add --dev <package>

# Update lock file
uv lock
```

## Project Configuration

### pyproject.toml Key Sections

- `[project]`: Package metadata and dependencies
- `[project.scripts]`: CLI entry point (`pdf-forms`)
- `[tool.ruff]`: Linting and formatting config
- `[tool.ty]`: Type checking config
- `[tool.pytest.ini_options]`: Test configuration
- `[tool.coverage]`: Coverage settings

## Troubleshooting

### pdfcpu not found

```bash
# Check if pdfcpu is installed
make check-pdfcpu
# or
uv run pdf-forms check
```

### Type checking errors

```bash
# Run ty with verbose output
uv run ty check --verbose
```

### Test failures

```bash
# Run with verbose output
uv run pytest -v --tb=short

# Run specific failing test
uv run pytest tests/test_extractor.py::TestClass::test_method -v
```

## Future Enhancements

Potential features to implement:
- PDF form filling functionality (`pdfcpu form fill`)
- CSV export format
- Batch processing multiple PDFs
- Form field validation using Pydantic models
- Async/await support for I/O operations

---

Last updated: 2026-03-06
