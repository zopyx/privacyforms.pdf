# PDF Representation Tutorial

This tutorial shows the quickest way to use the SurveyJS-oriented PDF representation
models defined in [`pdf_schema.py`](/Users/ajung/src/privacyforms.pdf/specs/pdf_schema.py:1).

## Goal

Build a small `PDFRepresentation`, validate it through normal model construction, and
serialize it to JSON for storage or downstream conversion.

## Steps

1. Create `ChoiceOption` entries for selectable fields.
2. Create `PDFField` entries.
3. Wrap them in a `PDFRepresentation`.
4. Validate by constructing the model.
5. Serialize to JSON.

## Python Example

```python
from pdf_schema import (
    ChoiceOption,
    FieldFlags,
    FieldLayout,
    PDFField,
    PDFRepresentation,
    RowGroup,
)

employment_type = PDFField(
    id="f-1",
    name="EmploymentType",
    title="Employment type",
    type="radiobuttongroup",
    layout=FieldLayout(page=0, x=120, y=220, width=180, height=22),
    value="full_time",
    choices=[
        ChoiceOption(value="full_time", text="Full time"),
        ChoiceOption(value="part_time", text="Part time"),
    ],
)

start_date = PDFField(
    id="f-2",
    name="StartDate",
    title="Start date",
    type="datefield",
    layout=FieldLayout(page=0, x=120, y=180, width=120, height=22),
    value="2026-04-17",
    format="yyyy-mm-dd",
)

accept_terms = PDFField(
    id="f-3",
    name="AcceptTerms",
    title="I accept the terms",
    type="checkbox",
    value=True,
    field_flags=FieldFlags(required=True),
)

document = PDFRepresentation(
    source="sample-form.pdf",
    fields=[employment_type, start_date, accept_terms],
    rows=[
        RowGroup(fields=[employment_type], page_index=0),
        RowGroup(fields=[start_date], page_index=0),
        RowGroup(fields=[accept_terms], page_index=0),
    ],
)

print(document.get_field_by_id("f-2"))
print(document.get_field_by_name("AcceptTerms"))
```

## JSON Serialization

Use Pydantic serialization methods to emit JSON:

```python
json_text = document.model_dump_json(indent=2)
print(json_text)
```

If you want a Python dictionary first:

```python
payload = document.model_dump()
```

Serialization notes:

- `None` values are included by default unless you pass `exclude_none=True`
- nested models such as `FieldLayout` and `ChoiceOption` serialize automatically
- the JSON output is designed for API exchange and storage, not for lossless PDF
  round-tripping

## Example JSON

```json
{
  "spec_version": "1.0",
  "source": "sample-form.pdf",
  "fields": [
    {
      "name": "EmploymentType",
      "title": "Employment type",
      "id": "f-1",
      "type": "radiobuttongroup",
      "field_flags": null,
      "layout": {
        "page": 0,
        "x": 120,
        "y": 220,
        "width": 180,
        "height": 22
      },
      "default_value": null,
      "value": "full_time",
      "choices": [
        {
          "value": "full_time",
          "text": "Full time",
          "source_name": null
        },
        {
          "value": "part_time",
          "text": "Part time",
          "source_name": null
        }
      ],
      "format": null,
      "max_length": null,
      "textarea_rows": null,
      "textarea_cols": null
    }
  ],
  "rows": []
}
```
