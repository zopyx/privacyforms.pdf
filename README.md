# privacyforms-pdf

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/badge/uv-managed-purple.svg)](https://github.com/astral-sh/uv)

Python library for extracting and filling PDF forms using [pypdf](https://pypdf.readthedocs.io/).

## Features

- Extract form data from PDF files using pure Python (no external dependencies)
- Fill PDF forms programmatically
- Extract field geometry (position and size) information
- Command-line interface with multiple commands
- Full type hints and comprehensive test coverage (99%)
- Support for all form field types (text, date, checkbox, radio button groups, etc.)

## Requirements

- Python 3.14+
- pypdf >= 5.0

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd privacyforms-pdf

# Install with uv
uv sync
```

## Quick Start

### Check CLI is ready

```bash
pdf-forms check
```

### Command Line Usage

```bash
# Check if a PDF contains a form
pdf-forms info form.pdf

# List all form fields
pdf-forms list-fields form.pdf

# Get a specific field value
pdf-forms get-value form.pdf "Field Name"

# Extract form data to JSON
pdf-forms extract form.pdf -o output.json

# Extract form data to stdout
pdf-forms extract form.pdf

# Fill a form from JSON (validates before filling)
pdf-forms fill-form form.pdf data.json -o filled.pdf

# Fill a form without validation
pdf-forms fill-form form.pdf data.json -o filled.pdf --no-validate

# Fill a form in-place (modifies original)
pdf-forms fill-form form.pdf data.json

# Fill with strict mode (requires all form fields)
pdf-forms fill-form form.pdf data.json -o filled.pdf --strict
```

#### JSON Format

The `fill-form` command accepts a simple key:value JSON format where keys are field names and values are the values to fill:

```json
{
  "Candidate Name": "John Smith",
  "Position": "Software Engineer",
  "Start date": "2025-06-01",
  "Full time": true,
  "Diploma or GED": "Yes"
}
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

# Fill a form using simple key:value format
form_data = {
    "Candidate Name": "John Smith",
    "Position": "Software Engineer",
    "Full time": True,
    "Start date": "2025-06-01"
}
extractor.fill_form("form.pdf", form_data, "filled.pdf")

# Or fill from a JSON file
extractor.fill_form_from_json("form.pdf", "data.json", "filled.pdf")

# Validate data before filling (returns list of errors)
errors = extractor.validate_form_data("form.pdf", form_data)
if errors:
    print("Validation errors:", errors)
```

## API Reference

### `PDFFormExtractor`

The main class for extracting and filling PDF form data.

#### Constructor

```python
extractor = PDFFormExtractor(
    timeout_seconds: float = 30.0,
    extract_geometry: bool = True
)
```

- `timeout_seconds`: Timeout for operations (kept for API compatibility).
- `extract_geometry`: Whether to extract field geometry information.

#### Methods

- `has_form(pdf_path: str | Path) -> bool`: Check if a PDF contains a form.
- `extract(pdf_path: str | Path) -> PDFFormData`: Extract form data from a PDF.
- `extract_to_json(pdf_path: str | Path, output_path: str | Path) -> None`: Export form data to a JSON file.
- `list_fields(pdf_path: str | Path) -> list[PDFField]`: List all form fields in a PDF.
- `get_field_value(pdf_path: str | Path, field_name: str) -> str | bool | None`: Get the value of a specific form field.
- `get_field_by_id(pdf_path: str | Path, field_id: str) -> PDFField | None`: Get a form field by its ID.
- `get_field_by_name(pdf_path: str | Path, field_name: str) -> PDFField | None`: Get a form field by its name.
- `validate_form_data(pdf_path: str | Path, form_data: dict, *, strict: bool = False, allow_extra_fields: bool = False) -> list[str]`: Validate form data (simple key:value format).
- `fill_form(pdf_path: str | Path, form_data: dict, output_path: str | Path | None = None, *, validate: bool = True) -> Path`: Fill a PDF form with data.
- `fill_form_from_json(pdf_path: str | Path, json_path: str | Path, output_path: str | Path | None = None, *, validate: bool = True) -> Path`: Fill a PDF form with data from a JSON file.

### Data Classes

#### `PDFFormData`

Represents extracted PDF form data.

- `source: Path`: Path to the source PDF file.
- `pdf_version: str`: Version of the PDF.
- `has_form: bool`: Whether the PDF contains a form.
- `fields: list[PDFField]`: List of form fields.
- `raw_data: dict[str, Any]`: The raw data from pypdf.

#### `PDFField`

Represents a single form field.

- `name: str`: The name of the field.
- `id: str`: The unique identifier of the field.
- `field_type: str`: The type of the form field (e.g., 'textfield', 'checkbox').
- `value: str | bool`: The current value of the field.
- `pages: list[int]`: List of pages where this field appears.
- `locked: bool`: Whether the field is locked.
- `geometry: FieldGeometry | None`: Optional geometry information (position and size).
- `format: str | None`: Date format for datefield types.
- `options: list[str]`: Available options for radiobuttongroup, combobox, listbox types.

#### `FieldGeometry`

Represents the geometry (position and size) of a form field.

- `page: int`: 1-based page number where field appears.
- `rect: tuple[float, float, float, float]`: Bounding box as (x1, y1, x2, y2) in PDF points.
- `x: float`: Left coordinate.
- `y: float`: Bottom coordinate (PDF coordinate system).
- `width: float`: Field width in points.
- `height: float`: Field height in points.
- `units: str`: Unit of measurement (always "pt" for points).

### JSON Export Format

When using `pdf-forms extract` or `extract_to_json()`, the output JSON has the following structure:

```json
{
  "source": "path/to/form.pdf",
  "pdf_version": "1.7",
  "has_form": true,
  "fields": [
    {
      "name": "Field Name",
      "id": "1",
      "field_type": "textfield",
      "value": "Field Value",
      "pages": [1],
      "locked": false,
      "geometry": {
        "page": 1,
        "rect": [53.0, 1077.0, 414.0, 1104.0],
        "x": 53.0,
        "y": 1077.0,
        "width": 361.0,
        "height": 27.0,
        "units": "pt"
      },
      "format": null,
      "options": []
    }
  ]
}
```

**Field Types:**
- `textfield`: Text input fields
- `datefield`: Date input fields (may include `format` attribute)
- `checkbox`: Boolean/checkbox fields (value is `true` or `false`)
- `radiobuttongroup`: Radio button groups (may include `options` array)
- `combobox`: Dropdown/combo boxes (may include `options` array)
- `listbox`: List selection boxes (may include `options` array)
- `signature`: Signature fields

**Geometry:**
The `geometry` object contains the field's position and size in PDF points (1/72 inch):
- `rect`: Array of `[x0, y0, x1, y1]` coordinates
- `x`, `y`: Bottom-left corner position
- `width`, `height`: Field dimensions
- Note: PDF coordinates have origin (0,0) at bottom-left of the page
- `width: float`: Field width in points.
- `height: float`: Field height in points.

### Exceptions

- `PDFFormError`: Base exception for PDF form related errors.
- `PDFFormNotFoundError`: Raised when the PDF does not contain any forms.
- `FormValidationError`: Raised when form data validation fails.
- `FieldNotFoundError`: Raised when a field is not found in the form.

**Note:** For backwards compatibility, the following aliases are still available but deprecated:
- `PDFCPUError` (alias for `PDFFormError`)
- `PDFCPUNotFoundError` (alias for `PDFFormError`)
- `PDFCPUExecutionError` (alias for `PDFFormError`)

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
uv run ty check
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
