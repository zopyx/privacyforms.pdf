# AGENTS.md - Project Context for AI Agents

## Project Overview

**privacyforms-pdf** is a Python library for parsing and filling PDF forms using [pypdf](https://pypdf.readthedocs.io/).

- **Author**: Andreas Jung <info@zopyx.com>
- **Python Version**: 3.12+
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **License**: MIT

## Architecture

```
privacyforms_pdf/
├── __init__.py          # Public API exports
├── schema.py            # Canonical PDFRepresentation schema
├── schema_layout.py     # Layout and row grouping helpers
├── parser.py            # PDF form parser (parse_pdf, extract_pdf_form)
├── extractor.py         # PDFFormExtractor class - core functionality
├── filler.py            # FormFiller class - pypdf form filling
├── hooks.py             # Pluggy hook specifications
├── commands/            # Built-in CLI command plugins
│   ├── pdf_fill_form.py
│   ├── pdf_parse.py
│   ├── pdf_verify_data.py
│   ├── pdf_verify_json.py
│   └── ...
└── cli.py               # Click-based CLI; loads commands via pluggy
```

### Core Classes

- **PDFFormExtractor**: Main high-level class for validation and filling
  - Uses pypdf for all PDF operations
  - Handles all PDF form field types (textfield, datefield, checkbox, radiobuttongroup, etc.)
  - Provides methods: `extract()`, `extract_to_json()`, `list_fields()`, `get_field_by_id()`, `get_field_by_name()`, `get_field_value()`, `has_form()`, `fill_form()`, `fill_form_from_json()`, `validate_form_data()`
- **Parse API**: Function-based read surface
  - `parse_pdf()`
  - `extract_pdf_form()`
  - Returns `PDFRepresentation`
- **Pluggy Plugin System**: CLI commands are loaded dynamically via `pluggy`
  - Hook specification: `PDFFormsCommandsSpec.register_commands()`
  - Built-in commands are registered as `privacyforms_pdf.commands` entry points
  - Third-party packages can extend the CLI by implementing the same hook

- **PDFRepresentation**: Canonical Pydantic schema for extracted form data (replaces internal PDFFormData)
- **PDFField** (schema.py): Rich Pydantic model with `field_flags`, `choices`, `layout`, `title`, etc.
- **FieldLayout**: Pydantic model representing field position and size (int-based, replaces FieldGeometry)
- **RowGroup**: Visual row groupings derived from layout analysis


### Exceptions

- `PDFFormError`: Base exception
- `PDFFormNotFoundError`: PDF has no form
- `FormValidationError`: Form data validation failed
- `FieldNotFoundError`: Field not found in form

## Tech Stack

| Category | Tool | Command |
|----------|------|---------|
| Package Manager | uv | `uv sync`, `uv add <pkg>` |
| Linter/Formatter | Ruff | `uv run ruff check .`, `uv run ruff format .` |
| Type Checker | ty | `uv run ty check` |
| Testing | pytest + pytest-cov | `uv run pytest` |
| CLI Framework | Click | Defined in `cli.py` |
| Plugin System | pluggy | Commands loaded via entry points |
| Data Validation | Pydantic | For form field models |
| PDF Library | pypdf | Pure Python PDF manipulation |

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

- **Typing**: All code must have complete type hints (`ty` is the configured checker)
- **Linting**: Ruff with line length 100, Python 3.13 target
- **Testing**: Minimum 90% coverage required (currently 99%)
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
make upload         # Upload to PyPI (with twine)
make upload-test    # Upload to TestPyPI (with twine)
```

## Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py                    # pytest fixtures
├── test_extractor.py              # Tests for PDFFormExtractor
├── test_filler.py                 # Tests for FormFiller
├── test_specs.py                  # Tests for schema and parser
├── test_cli.py                    # Tests for CLI group
└── commands/
    ├── test_pdf_parse.py
    ├── test_pdf_verify_data.py
    ├── test_pdf_verify_json.py
    └── ...
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
- `pypdf.PdfReader` for PDF reading operations
- `pypdf.PdfWriter` for PDF writing operations
- File system operations where appropriate

## CI/CD

### GitHub Actions Workflows

| Workflow | File | Trigger |
|----------|------|---------|
| CI | `.github/workflows/ci.yml` | Push/PR to main/master |

### CI Jobs

1. **Lint & Format**: Ruff checks
2. **Type Check**: ty strict mode
3. **Test**: Python matrix includes 3.12, 3.13, 3.14, and 3.14t

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
from pypdf import PdfReader, PdfWriter

# Local
from .extractor import PDFFormExtractor
```

### Function Signatures

```python
def parse_pdf(
    pdf_path: str | Path,
    source: str | None = None,
    reader: PdfReader | None = None,
) -> PDFRepresentation:
    """Parse a PDF into the canonical representation.

    Args:
        pdf_path: Path to the PDF file.
        source: Optional source identifier.
        reader: Optional preconstructed PdfReader.

    Returns:
        PDFRepresentation containing normalized field and row data.
    """
```

### Error Handling

```python
try:
    result = self._run_command([...])
except PDFFormError as e:
    # Handle specific error
    raise click.ClickException(f"Failed: {e}") from e
```

## External Dependencies

### Python Dependencies

See `pyproject.toml`:
- `click` - CLI framework
- `pydantic` - Data validation
- `pypdf>=5` - PDF manipulation library

## Common Tasks

### Add a New CLI Command

1. Create `privacyforms_pdf/commands/pdf_<name>.py` with a `@click.command(name="...")` function
2. Add a `register_commands()` function decorated with `@hookimpl` that returns the command(s)
3. Register the module as a `privacyforms_pdf.commands` entry point in `pyproject.toml`
4. Use Click's argument/option decorators and handle errors with `click.ClickException`
5. Add tests in `tests/commands/test_pdf_<name>.py`

Example entry point in `pyproject.toml`:
```toml
[project.entry-points."privacyforms_pdf.commands"]
my_command = "privacyforms_pdf.commands.pdf_my_command"
```

### Add a New Extractor Method

1. Add method to `PDFFormExtractor` in `extractor.py`
2. Use `PdfReader`/`PdfWriter` for pypdf operations
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
- CSV export format
- Batch processing multiple PDFs
- Form field validation using Pydantic models
- Async/await support for I/O operations
- PDF form creation from scratch

---

Last updated: 2026-04-17 (v0.2.0)
