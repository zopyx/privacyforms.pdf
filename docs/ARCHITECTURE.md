# privacyforms-pdf — Technical Documentation

> **Version:** 0.2.0
> **Scope:** Current package architecture, public API, CLI wiring, and data flow.

## Architecture Overview

`privacyforms-pdf` is a pure-Python library built on top of `pypdf`. The codebase has two primary workflows:

- parse a PDF into a canonical `PDFRepresentation`
- fill a PDF from simple key/value data

The package deliberately separates those concerns:

- `parser.py` performs extraction and normalization
- `schema.py` defines the canonical document model
- `schema_layout.py` derives layout hints and row groupings
- `filler.py` handles PDF mutation and appearance synchronization
- `extractor.py` provides the higher-level validation/fill facade
- `cli.py` loads Click commands through `pluggy`

## Package Structure

```text
privacyforms_pdf/
├── __init__.py
├── schema.py
├── schema_layout.py
├── parser.py
├── extractor.py
├── filler.py
├── hooks.py
├── utils.py
├── cli.py
├── backends/
└── commands/
    ├── __init__.py
    ├── utils.py
    ├── pdf_parse.py
    ├── pdf_fill_form.py
    ├── pdf_info.py
    ├── pdf_verify_data.py
    └── pdf_verify_json.py
```

## Main Components

### `schema.py`

Defines the canonical document model used across parse and verification flows:

- `PDFRepresentation`
- `PDFField`
- `FieldFlags`
- `FieldLayout`
- `ChoiceOption`
- `RowGroup`

This is the central data contract of the project.

### `parser.py`

Responsible for:

- reading PDFs with `pypdf.PdfReader`
- normalizing field types and values
- extracting structured choice data
- resolving field layout from widget annotations
- building row groups from layout analysis

Primary public entry points:

- `parse_pdf()`
- `extract_pdf_form()`

### `schema_layout.py`

Contains helper functions that convert raw annotation geometry into:

- `FieldLayout`
- visual `RowGroup` collections

### `filler.py`

Contains `FormFiller`, the low-level writer used for:

- text/checkbox/radio/listbox filling
- widget appearance synchronization
- fallbacks when `pypdf` appearance generation is insufficient

### `extractor.py`

Contains `PDFFormService`, the higher-level facade for read, validation, and fill workflows:

- `extract()`
- `extract_to_json()`
- `list_fields()`
- `get_field_by_id()`
- `get_field_by_name()`
- `get_field_value()`
- `has_form()`
- `validate_form_data()`
- `fill_form()`
- `fill_form_from_json()`

It also re-exports exceptions and a few helper utilities for compatibility.

### `cli.py` And `commands/`

The CLI is implemented with Click and loaded through `pluggy` entry points. Built-in commands currently include:

- `parse`
- `fill-form`
- `info`
- `verify-data`
- `verify-json`

## Public API

### Parse API

The package exposes both function-based and facade-based read APIs.

Function-based:

- `extract_pdf_form(pdf_filename: Path | str) -> PDFRepresentation`
- `parse_pdf(pdf_path: Path | str, source: str | None = None, reader: PdfReader | None = None) -> PDFRepresentation`

Facade-based:

- `PDFFormService.extract(pdf_path, source=None)`
- `PDFFormService.extract_to_json(pdf_path, output_path, source=None)`
- `PDFFormService.list_fields(pdf_path)`
- `PDFFormService.get_field_by_id(pdf_path, field_id)`
- `PDFFormService.get_field_by_name(pdf_path, field_name)`
- `PDFFormService.get_field_value(pdf_path, field_name)`

### Fill API

The current fill/validation API is class-based:

- `PDFFormService.has_form(pdf_path)`
- `PDFFormService.validate_form_data(pdf_path, form_data, strict=False, allow_extra_fields=False, key_mode="name" | "id" | "auto")`
- `PDFFormService.fill_form(pdf_path, form_data, output_path=None, validate=True, key_mode="name" | "id" | "auto")`
- `PDFFormService.fill_form_from_json(pdf_path, json_path, output_path=None, validate=True, key_mode="name" | "id" | "auto")`

Preferred contract:

- field IDs are the canonical external key format
- field names are supported as convenience inputs
- `auto` mode exists for compatibility and mixed payloads

### Low-Level Writer

`FormFiller.fill()` is available as a lower-level writer API, but the primary supported entry point for normal use is `PDFFormService`.

## Data Model

### `PDFRepresentation`

Top-level document model:

- `spec_version: str`
- `source: str | None`
- `fields: list[PDFField]`
- `rows: list[RowGroup]`

### `PDFField`

Normalized field model:

- `name`
- `title`
- `id`
- `type`
- `field_flags`
- `layout`
- `default_value`
- `value`
- `choices`
- `format`
- `max_length`
- `textarea_rows`
- `textarea_cols`

Supported field types:

- `textfield`
- `textarea`
- `datefield`
- `checkbox`
- `radiobuttongroup`
- `combobox`
- `listbox`
- `signature`

### `FieldLayout`

Compact layout hints derived from widget rectangles:

- `page`
- `x`
- `y`
- `width`
- `height`

### `RowGroup`

Represents visually grouped fields on the same page row. In JSON form, rows serialize field references as field IDs.

## Core Workflows

### Parse Flow

1. `parse_pdf()` opens the PDF with `PdfReader`
2. `reader.get_fields()` returns the form field map
3. page annotations are scanned to resolve widget rectangles
4. raw PDF fields are normalized into `PDFField`
5. layout data is converted into `FieldLayout`
6. visual rows are built from field layout
7. the result is returned as `PDFRepresentation`

### Fill Flow

1. `PDFFormService.fill_form()` validates the PDF path
2. `has_form()` ensures the PDF contains form fields
3. `validate_form_data()` optionally checks field names and checkbox value types
4. `FormFiller.fill()` writes values via `PdfWriter`
5. radio/listbox widget states are synchronized for viewer compatibility
6. the filled PDF is written to disk

## CLI Architecture

The CLI is intentionally thin.

### `parse`

- calls `extract_pdf_form()`
- writes `representation.to_compact_json()`
- prints a row summary

### `verify-json`

- reads a JSON file
- validates it with `PDFRepresentation.model_validate_json()`

### `verify-data`

- validates a parsed representation JSON file
- checks that sample data keys match parsed field IDs, field names, or both

Important:

- `verify-data` supports `--key-mode id|name|auto`
- `fill-form` supports `--field-keys id|name|auto`
- `auto` mode accepts a mixture of field names and canonical field IDs
- `id` is the preferred machine-facing mode

### `fill-form`

- reads simple JSON key/value data
- supports field names, field IDs, or mixed keys
- prefers field IDs as the canonical payload format
- optionally validates field names and checkbox value types
- fills the target PDF

### `info`

- reports whether a PDF contains a form

## Error Handling

All project-specific exceptions derive from `PDFFormError`:

- `PDFFormNotFoundError`
- `FieldNotFoundError`
- `FormValidationError`

CLI commands convert those exceptions into `click.ClickException` for user-facing errors.

## Extension Model

CLI command extension is based on `pluggy`.

- hook spec: `PDFFormsCommandsSpec.register_commands()`
- built-in commands are registered under the `privacyforms_pdf.commands` entry-point group
- third-party packages can register additional Click commands using the same hook

## Design Notes

### Why The Parse API Is Function-Based

The codebase currently treats parsing as schema production rather than as an instance-oriented extractor method. That keeps the read path simple and makes `PDFRepresentation` the stable parse result.

### Why The Fill API Is Class-Based

The fill path benefits from a small facade that can:

- validate inputs
- centralize exception behavior
- delegate writing details to `FormFiller`

### Compatibility Layer

`extractor.py` still exports a few helper functions and delegated wrappers for compatibility and tests. The canonical read model is `PDFRepresentation`, and the extractor facade now delegates to that model rather than maintaining a separate read structure.
