# privacyforms-pdf — Technical Documentation

> **Version:** 0.1.3  
> **Scope:** API reference, architecture overview, data models, and execution workflows.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Package Structure](#package-structure)
3. [Data Models](#data-models)
4. [Core Workflows](#core-workflows)
5. [CLI Architecture](#cli-architecture)
6. [Error Handling](#error-handling)
7. [Diagram Assets](#diagram-assets)

---

## Architecture Overview

`privacyforms-pdf` is a pure-Python library built on top of [`pypdf`](https://pypdf.readthedocs.io/). It exposes both a programmatic API (`PDFFormExtractor`) and a command-line interface (`pdf-forms`). All PDF I/O is delegated to `pypdf`; the library itself contains no native extensions.

### Component Diagram

```mermaid
graph LR
    subgraph "Client Layer"
        A[Python Application]
        B[pdf-forms CLI]
    end

    subgraph "privacyforms-pdf Library"
        C[PDFFormExtractor]
        D[PDFField Models]
        E[CLI Module]
    end

    subgraph "External Dependencies"
        F[pypdf<br/>PdfReader / PdfWriter]
    end

    subgraph "I/O"
        G[PDF Files]
        H[JSON Files]
    end

    A -->|import| C
    B -->|click| E
    E -->|uses| C
    C -->|reads/writes| F
    F -->|processes| G
    C -->|produces| H
    D -.->|validated by| C
```

### Package Structure

```mermaid
graph TD
    Root[privacyforms-pdf/] --> P[privacyforms_pdf/]
    Root --> T[tests/]
    Root --> S[samples/]
    Root --> D[demo/]
    Root --> G[.github/workflows/]
    Root --> Py[pyproject.toml]

    P --> I[__init__.py]
    P --> E[extractor.py]
    P --> CLI[cli.py]

    T --> C[conftest.py]
    T --> TE[test_extractor.py]
    T --> TC[test_cli.py]
```

---

## Data Models

### Class Diagram

```mermaid
classDiagram
    class PDFFormExtractor {
        -float _timeout_seconds
        -bool _extract_geometry
        +__init__(timeout_seconds, extract_geometry)
        +has_form(pdf_path) bool
        +extract(pdf_path) PDFFormData
        +extract_to_json(pdf_path, output_path)
        +list_fields(pdf_path) list~PDFField~
        +get_field_value(pdf_path, field_name) str|bool|None
        +get_field_by_id(pdf_path, field_id) PDFField|None
        +get_field_by_name(pdf_path, field_name) PDFField|None
        +validate_form_data(pdf_path, form_data, strict, allow_extra_fields) list~str~
        +fill_form(pdf_path, form_data, output_path, validate) Path
        +fill_form_from_json(pdf_path, json_path, output_path, validate) Path
        -_validate_pdf_path(pdf_path)
        -_get_field_type(field) str$
        -_get_field_value(field) str|bool$
        -_get_field_options(field) list~str~$
        -_extract_widgets_info(reader) dict
    }

    class PDFFormData {
        +Path source
        +str pdf_version
        +bool has_form
        +list~PDFField~ fields
        +dict raw_data
        +to_json() str
        +to_dict() dict
    }

    class PDFField {
        +str name
        +str id
        +str field_type
        +str|bool value
        +list~int~ pages
        +bool locked
        +FieldGeometry|None geometry
        +str|None format
        +list~str~ options
        +model_dump() dict
    }

    class FieldGeometry {
        +int page
        +tuple rect
        +float x
        +float y
        +float width
        +float height
        +str units
        +model_dump() dict
    }

    class FormField {
        +str field_type
        +list~int~ pages
        +str id
        +str name
        +str|bool value
        +bool locked
    }

    class PDFFormError
    class PDFFormNotFoundError
    class FieldNotFoundError
    class FormValidationError

    PDFFormExtractor --> PDFFormData : creates
    PDFFormExtractor --> PDFField : creates
    PDFFormData --> PDFField : contains
    PDFField --> FieldGeometry : optional
    PDFFormError <|-- PDFFormNotFoundError
    PDFFormError <|-- FieldNotFoundError
    PDFFormError <|-- FormValidationError
```

### Model Descriptions

| Model | Purpose |
|-------|---------|
| `PDFFormExtractor` | Central orchestrator for reading, validating, and writing PDF forms. |
| `PDFFormData` | Container for extracted form metadata (version, fields, raw data). |
| `PDFField` | Pydantic v2 model representing a single form field with optional geometry. |
| `FieldGeometry` | Pydantic v2 model holding a field’s bounding box and page location. |
| `FormField` | Legacy plain class kept for backwards compatibility. |

---

## Core Workflows

### Form Extraction Sequence

The `extract()` method performs a two-pass scan:
1. **Field scan** via `PdfReader.get_fields()`
2. **Widget scan** via page annotations (`/Annots`) to resolve page numbers and geometry.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant E as PDFFormExtractor
    participant V as _validate_pdf_path
    participant R as pypdf.PdfReader
    participant W as _extract_widgets_info
    participant F as PDFField
    participant D as PDFFormData

    C->>E: extract(pdf_path)
    E->>V: _validate_pdf_path(pdf_path)
    V-->>E: OK
    E->>R: PdfReader(str(pdf_path))
    E->>R: get_fields()
    R-->>E: dict[field_name, field_data]

    E->>W: _extract_widgets_info(reader)
    loop For each page with /Annots
        W->>W: scan widget annotations
        W->>W: extract page + geometry
    end
    W-->>E: widget_info

    loop For each field
        E->>E: _get_field_type(field_data)
        E->>E: _get_field_value(field_data)
        E->>E: _get_field_options(field_data)
        E->>F: PDFField(name, type, value, pages, geometry, ...)
        F-->>E: pdffield
    end

    E->>E: _build_raw_data_structure(fields, source)
    E->>D: PDFFormData(source, version, has_form, fields, raw_data)
    D-->>E: form_data
    E-->>C: PDFFormData
```

### Form Filling Sequence

Form filling creates a **new PDF stream** via `PdfWriter.append(reader)` and updates widget values page-by-page.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant E as PDFFormExtractor
    participant V as _validate_pdf_path
    participant H as has_form
    participant Val as validate_form_data
    participant R as pypdf.PdfReader
    participant W as pypdf.PdfWriter
    participant P as PDF File

    C->>E: fill_form(pdf, data, output, validate=True)
    E->>V: _validate_pdf_path(pdf)
    V-->>E: OK
    E->>H: has_form(pdf)
    H-->>E: true

    opt validate=True
        E->>Val: validate_form_data(pdf, data)
        Val-->>E: [] (no errors)
    end

    E->>R: PdfReader(str(pdf))
    E->>W: PdfWriter()
    E->>W: writer.append(reader)

    loop Convert data values
        E->>E: bool -> "/Yes" / "/Off"
        E->>E: other -> str(value)
    end

    loop For each page in writer
        E->>W: update_page_form_field_values(page, field_values)
    end

    E->>P: write(output_file)
    W->>P: write(f)
    P-->>E: filled PDF
    E-->>C: Path(output_file)
```

---

## CLI Architecture

The CLI is implemented with **Click** and delegates all heavy work to `PDFFormExtractor`. Each subcommand is a thin wrapper that:
1. Instantiates an extractor via `create_extractor()`
2. Calls the corresponding library method
3. Formats and prints the result (JSON, table, or plain text)
4. Translates library exceptions into `click.ClickException`

### CLI Command Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant Cl as Click CLI
    participant C as CLI Module
    participant Ex as create_extractor
    participant E as PDFFormExtractor

    U->>Cl: pdf-forms extract form.pdf -o out.json
    Cl->>C: extract(pdf_path, output, raw)
    C->>Ex: create_extractor()
    Ex-->>C: PDFFormExtractor()
    C->>E: extract(pdf_path)
    E-->>C: PDFFormData
    C->>C: json.dump(form_data.to_dict(), f)
    C-->>Cl: success message
    Cl-->>U: stdout + file written
```

### Command Mapping

| CLI Command | Library Method | Output Format |
|-------------|----------------|---------------|
| `check` | — | Human-readable status |
| `info <pdf>` | `has_form()` | `✓` / `✗` message |
| `extract <pdf>` | `extract()` | JSON (stdout or file) |
| `list-fields <pdf>` | `list_fields()` | Aligned table |
| `get-value <pdf> <field>` | `get_field_value()` | Plain value |
| `fill-form <pdf> <json>` | `fill_form_from_json()` | Filled PDF file |

---

## Error Handling

All library exceptions inherit from `PDFFormError`. The CLI catches these and re-raises them as `click.ClickException`, ensuring a clean exit code and user-friendly message.

### Exception Hierarchy

```mermaid
graph TD
    A[Exception] --> B[PDFFormError]
    B --> C[PDFFormNotFoundError]
    B --> D[FieldNotFoundError]
    B --> E[FormValidationError]
    B -.->|deprecated alias| F[PDFCPUError]
    B -.->|deprecated alias| G[PDFCPUNotFoundError]
    B -.->|deprecated alias| H[PDFCPUExecutionError]
```

### Exception Usage Matrix

| Exception | Raised By | Typical Cause |
|-----------|-----------|---------------|
| `PDFFormNotFoundError` | `extract()`, `fill_form()` | PDF contains no AcroForm. |
| `FormValidationError` | `fill_form()` with `validate=True` | Unknown field, type mismatch, or strict-mode missing field. |
| `FieldNotFoundError` | *(public API)* | Explicit lookup by name/ID failed. |
| `PDFCPUError` aliases | *(deprecated)* | Backwards compatibility with pre-pypdf versions. |

---

## Diagram Assets

For online documentation and GitHub rendering, SVG exports of every diagram are provided in the `docs/diagrams/` directory.

| Diagram | Markdown Embed | SVG File |
|---------|---------------|----------|
| Component Diagram | above | `diagrams/architecture-components.svg` |
| Package Structure | above | `diagrams/package-structure.svg` |
| Class Diagram | above | `diagrams/class-diagram.svg` |
| Extraction Sequence | above | `diagrams/sequence-extract.svg` |
| Filling Sequence | above | `diagrams/sequence-fill.svg` |
| CLI Sequence | above | `diagrams/sequence-cli.svg` |
| Exception Hierarchy | above | `diagrams/exception-hierarchy.svg` |

> **Tip:** If your documentation platform (e.g., MkDocs, Docusaurus) does not support Mermaid natively, reference the SVG files directly with standard Markdown image syntax:
> ```markdown
> ![Component Diagram](diagrams/architecture-components.svg)
> ```
