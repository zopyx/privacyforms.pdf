# PDF Representation Specification

## Purpose

This document defines the intermediate representation used to convert fillable PDF forms
into SurveyJS-compatible structures.

This format is intentionally not a full PDF or AcroForm serialization. It exists to
preserve the information needed for:

- field classification
- field ordering and grouping
- source traceability
- value extraction
- choice extraction
- downstream conversion into SurveyJS questions and pages

## Non-Goals

This representation does not aim to preserve:

- arbitrary PDF object dictionaries
- appearance streams
- actions and scripting
- full widget annotation structure
- round-trip PDF fidelity
- the entire ISO 32000 field model

If a property does not materially improve SurveyJS conversion, it should usually not be
included.

## Design Principles

1. Expose a stable top-level API object.
2. Normalize PDF field types into a small conversion-friendly set.
3. Preserve the original field name for traceability.
4. Represent values according to question semantics, not PDF internals.
5. Use compact structured objects for layout and choices.
6. Prefer explicit flags over raw bitfields.

## Top-Level API

The representation is built from:

- `PDFRepresentation`
- `PDFField`
- `FieldFlags`
- `ChoiceOption`
- `FieldLayout`
- `RowGroup`

`PDFRepresentation` is the top-level document object. Consumers should validate and
exchange this object rather than loose field lists.

## `PDFRepresentation`

### Fields

#### `spec_version: str`

Version of this intermediate format.

Current value:

- `1.0`

#### `source: str | None`

Optional path, URL, or other identifier for the source PDF document.

#### `fields: list[PDFField]`

The normalized fillable fields extracted from the PDF.

#### `rows: list[RowGroup]`

Optional row groupings derived from layout analysis.

These help preserve rough document structure during conversion.

## Supported Field Types

The normalized field types are:

- `textfield`
- `textarea`
- `datefield`
- `checkbox`
- `radiobuttongroup`
- `combobox`
- `listbox`
- `signature`

These are the field types that map naturally into SurveyJS.

## Unsupported Types

The following PDF concepts are currently out of scope:

- `pushbutton`
- `barcode`
- PDF-only control widgets with no SurveyJS question equivalent

They may exist in source PDFs, but they are not first-class members of this conversion
format.

## `PDFField`

`PDFField` is the central unit of the representation.

### Required fields

#### `name: str`

The original PDF field name.

Use this for:

- traceability
- debugging
- source-to-target mapping
- matching back to extracted PDF fields

This field should not be assumed to be user-facing text.

#### `id: str`

A stable unique identifier within the extracted representation.

#### `type: PDFFieldType`

The normalized field type.

Allowed values:

- `textfield`
- `textarea`
- `datefield`
- `checkbox`
- `radiobuttongroup`
- `combobox`
- `listbox`
- `signature`

### Optional fields

#### `title: str | None`

Optional user-facing title or label associated with the field.

This is the preferred source for SurveyJS question text when available.

#### `field_flags: FieldFlags | None`

Human-readable behavioral flags derived from the source PDF field flags.

These affect conversion decisions such as:

- required
- read-only
- multiline
- editable combo behavior
- multi-select list behavior

#### `layout: FieldLayout | None`

Compact layout hints used for:

- grouping
- ordering
- label-control association heuristics

This is intentionally not a full PDF geometry model.

#### `default_value: str | bool | list[str] | None`

Default value, if known.

#### `value: str | bool | list[str] | None`

Normalized current value of the field.

Expected forms by field type:

- `textfield`: `str | None`
- `textarea`: `str | None`
- `datefield`: `str | None`
- `checkbox`: `bool | None`
- `radiobuttongroup`: `str | None`
- `combobox`: `str | None`
- `listbox`: `str | list[str] | None`
- `signature`: `str | None`

List values should only be used for multi-select cases.

#### `choices: list[ChoiceOption]`

Structured options for choice-based fields.

Applies mainly to:

- `radiobuttongroup`
- `combobox`
- `listbox`

#### `format: str | None`

Optional display or parsing format hint.

Currently this is mainly intended for:

- `datefield`

Examples:

- `yyyy-mm-dd`
- `mm/dd/yyyy`
- `dd.mm.yyyy`

#### `max_length: int | None`

Maximum character length for text-like inputs.

#### `textarea_rows: int | None`
#### `textarea_cols: int | None`

Optional UI hints for multiline text inputs.

## `FieldFlags`

`FieldFlags` exposes behavior-relevant PDF properties as booleans.

### General flags

- `read_only`
- `required`
- `no_export`

### Button-related flags

- `no_toggle_to_off`
- `radio`
- `pushbutton`

### Text-related flags

- `multiline`
- `password`
- `file_select`
- `do_not_spellcheck`
- `do_not_scroll`
- `comb`
- `rich_text`

### Choice-related flags

- `combo`
- `edit`
- `sort`
- `multi_select`
- `commit_on_sel_change`

These flags are included because they may influence normalization or SurveyJS mapping.

## `ChoiceOption`

`ChoiceOption` represents a selectable choice.

### Fields

#### `value: str`

Stored value used when the option is selected.

#### `text: str | None`

Optional user-facing label.

#### `source_name: str | None`

Optional raw identifier or token from the extraction layer.

## `FieldLayout`

`FieldLayout` provides compact conversion-oriented placement hints.

### Fields

#### `page: int | None`

Zero-based page index where the field appears.

#### `x: int | None`
#### `y: int | None`
#### `width: int | None`
#### `height: int | None`

Basic placement and size hints for ordering and grouping.

## `RowGroup`

`RowGroup` represents a collection of visually related fields that appear on one page row.

### Fields

#### `fields: list[PDFField]`

Ordered list of fields belonging to the same visual row.

#### `page_index: int`

Zero-based page index for the row.

## Normalization Rules

### Text fields

Use `textfield` for normal single-line textual input.

Use `textarea` when the field is conceptually multiline. This may be derived from:

- extractor logic
- `field_flags.multiline`

### Date fields

Use `datefield` only when the extractor has enough evidence that the field is intended to
hold a date.

If known, `format` should be included.

### Checkbox fields

Use `checkbox` for a binary yes/no or on/off value.

`value` should normally be:

- `true`
- `false`
- `null`

### Radio button groups

Use `radiobuttongroup` when the source field represents a single-selection set of options.

`choices` should contain the available options.
`value` should be a single selected string or `null`.

### Combo boxes

Use `combobox` for dropdown-style fields.

If the source permits free text entry, this should be reflected through:

- `field_flags.combo`
- `field_flags.edit`

### List boxes

Use `listbox` for visible list selection controls.

`value` may be:

- a single string
- a list of strings for multi-select
- `null`

If multi-select is supported, `field_flags.multi_select` should be set when known.

### Signature fields

Use `signature` for signature capture areas.

The exact content of `value` depends on extractor behavior. The important point is that
the field is typed distinctly so downstream logic can map it to a SurveyJS signature
component.

## SurveyJS Mapping Guidance

The default mapping direction is:

- `textfield` -> SurveyJS text question
- `textarea` -> SurveyJS comment question
- `datefield` -> SurveyJS text/date-oriented question
- `checkbox` -> SurveyJS boolean question
- `radiobuttongroup` -> SurveyJS radiogroup question
- `combobox` -> SurveyJS dropdown question
- `listbox` -> SurveyJS dropdown, tagbox, or checkbox-style question
- `signature` -> SurveyJS signature pad question

This representation intentionally leaves final converter choices open where SurveyJS offers
multiple target components.

## Validation Expectations

Consumers of this format should assume:

- `spec_version` is always present
- `name`, `id`, and `type` are always present on every field
- `value` may be absent or `null`
- `choices` may be empty even for choice fields when extraction is incomplete
- `layout` may be missing
- `field_flags` may be missing when flag parsing is unavailable
- `format` is optional even for `datefield`

## Validation Rules

The schema is designed to reject obviously inconsistent field definitions.

Important built-in checks include:

- field `id` and `name` must be non-empty
- `spec_version` must be non-empty
- layout values must be non-negative
- `format` is only valid for `datefield`
- `textarea_rows` and `textarea_cols` are only valid for `textarea`
- `choices` are only valid for `radiobuttongroup`, `combobox`, and `listbox`
- `checkbox.value` must be `bool | None`
- `textfield`, `textarea`, `datefield`, and `signature` values must be `str | None`
- `radiobuttongroup` and `combobox` values must be `str | None`
- list-valued `value` is only valid for `listbox`
- list-valued `listbox.value` requires `field_flags.multi_select == true`
- field ids must be unique within `PDFRepresentation`
- row groups may only reference fields that are present in `fields`

These rules are intended to catch schema misuse early while keeping the model practical for
conversion workflows.

## Tutorial

For a beginner-friendly walkthrough, see:

- [`TUTORIAL.md`](/Users/ajung/src/privacyforms.pdf/specs/TUTORIAL.md:1)

That file includes:

- a minimal end-to-end Python example
- JSON serialization examples
- an example JSON payload

## Recommended Future Extensions

Likely future improvements include:

- stronger validation rules per field type
- title extraction heuristics
- richer document metadata
- provenance and extraction warnings

## Current Schema Reference

The schema is defined in:

- [`pdf_schema.py`](/Users/ajung/src/privacyforms.pdf/specs/pdf_schema.py:1)

This document is the normative specification for the intended intermediate representation.
