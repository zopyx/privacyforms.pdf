# privacyforms-pdf

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/badge/uv-managed-purple.svg)](https://github.com/astral-sh/uv)

Python wrappers for pdfcpu to extract and fill PDF forms.

## Features

- Extract form data from PDF files using [pdfcpu](https://pdfcpu.io/)
- Programmatic API via `PDFFormExtractor` class
- Command-line interface with multiple commands
- Full type hints and comprehensive test coverage
- Support for all form field types (text, date, checkbox, radio button groups, etc.)

## Requirements

- Python 3.14+
- [pdfcpu](https://pdfcpu.io/install) must be installed on your system

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd privacyforms-pdf

# Install with uv
uv sync
```

## Quick Start

### Check if pdfcpu is installed

```bash
privacyforms check
```

### Command Line Usage

```bash
# Check if a PDF contains a form
privacyforms info form.pdf

# List all form fields
privacyforms list-fields form.pdf

# Get a specific field value
privacyforms get-value form.pdf "Field Name"

# Extract form data to JSON
privacyforms extract form.pdf -o output.json

# Extract form data to stdout
privacyforms extract form.pdf
```

### Python API

```python
from privacyforms_pdf import PDFFormExtractor

# Initialize the extractor
extractor = PDFFormExtractor()

# Extract form data
form_data = extractor.extract("form.pdf")

# Access form information
print(f"PDF Version: {form_data.pdf_version}")
print(f"Has Form: {form_data.has_form}")
print(f"Total Fields: {len(form_data.fields)}")

# Iterate over fields
for field in form_data.fields:
    print(f"{field.name}: {field.value}")

# Get specific field value
value = extractor.get_field_value("form.pdf", "Field Name")

# Check if PDF has a form
has_form = extractor.has_form("form.pdf")

# Export to JSON file
extractor.extract_to_json("form.pdf", "output.json")
```

## API Reference

### `PDFFormExtractor`

The main class for extracting PDF form data.

#### Constructor

```python
extractor = PDFFormExtractor(pdfcpu_path: str | None = None)
```

- `pdfcpu_path`: Optional path to the pdfcpu executable. If not provided, searches in system PATH.

#### Methods

- `check_pdfcpu() -> bool`: Check if pdfcpu is available and working.
- `get_pdfcpu_version() -> str`: Get the installed pdfcpu version.
- `has_form(pdf_path: str | Path) -> bool`: Check if a PDF contains a form.
- `extract(pdf_path: str | Path) -> PDFFormData`: Extract form data from a PDF.
- `extract_to_json(pdf_path: str | Path, output_path: str | Path) -> None`: Export form data to a JSON file.
- `list_fields(pdf_path: str | Path) -> list[FormField]`: List all form fields in a PDF.
- `get_field_value(pdf_path: str | Path, field_name: str) -> str | bool | None`: Get the value of a specific form field.

### Data Classes

#### `PDFFormData`

Represents extracted PDF form data.

- `source: Path`: Path to the source PDF file.
- `pdf_version: str`: Version of the PDF.
- `has_form: bool`: Whether the PDF contains a form.
- `fields: list[FormField]`: List of form fields.
- `raw_data: dict[str, Any]`: The raw JSON data from pdfcpu.

#### `FormField`

Represents a single form field.

- `field_type: str`: The type of the form field (e.g., 'textfield', 'checkbox').
- `pages: list[int]`: List of pages where this field appears.
- `id: str`: The unique identifier of the field.
- `name: str`: The name of the field.
- `value: str | bool`: The current value of the field.
- `locked: bool`: Whether the field is locked.

### Exceptions

- `PDFCPUError`: Base exception for pdfcpu related errors.
- `PDFCPUNotFoundError`: Raised when pdfcpu is not found on the system.
- `PDFCPUExecutionError`: Raised when pdfcpu execution fails.
- `PDFFormNotFoundError`: Raised when the PDF does not contain any forms.

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run linting
uv run ruff check .

# Run type checking
uv run pyright
```

### Project Structure

```
privacyforms-pdf/
├── privacyforms_pdf/       # Main package
│   ├── __init__.py         # Package exports
│   ├── extractor.py        # PDFFormExtractor implementation
│   └── cli.py              # Command-line interface
├── tests/                  # Test suite
│   ├── test_extractor.py   # Tests for extractor
│   └── test_cli.py         # Tests for CLI
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

## License

Copyright 2025 Andreas Jung (info@zopyx.com)
