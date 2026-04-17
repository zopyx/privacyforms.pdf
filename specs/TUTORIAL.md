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

## Example: Textarea and Combo Box

This example adds a multiline text area and an editable combo box:

```python
from pdf_schema import ChoiceOption, FieldFlags, FieldLayout, PDFField

comments = PDFField(
    id="f-4",
    name="Comments",
    title="Additional comments",
    type="textarea",
    layout=FieldLayout(page=0, x=80, y=120, width=280, height=80),
    value="Available to start in May.",
    textarea_rows=4,
    textarea_cols=40,
)

department = PDFField(
    id="f-5",
    name="Department",
    title="Preferred department",
    type="combobox",
    field_flags=FieldFlags(combo=True, edit=True),
    layout=FieldLayout(page=0, x=80, y=80, width=180, height=22),
    value="engineering",
    choices=[
        ChoiceOption(value="engineering", text="Engineering"),
        ChoiceOption(value="sales", text="Sales"),
        ChoiceOption(value="operations", text="Operations"),
    ],
)
```

## Example: Multi-select List Box

List-valued `listbox` fields require `field_flags.multi_select=True`:

```python
from pdf_schema import ChoiceOption, FieldFlags, PDFField

skills = PDFField(
    id="f-6",
    name="Skills",
    title="Skills",
    type="listbox",
    field_flags=FieldFlags(multi_select=True),
    value=["python", "pdf"],
    choices=[
        ChoiceOption(value="python", text="Python"),
        ChoiceOption(value="pdf", text="PDF processing"),
        ChoiceOption(value="cli", text="CLI tooling"),
    ],
)
```

Without `FieldFlags(multi_select=True)`, a list value would fail validation.

## Example: Lookup and Update a Field

After construction, you can retrieve fields by id or original name and update them:

```python
field = document.get_field_by_id("f-1")
if field is not None:
    field.value = "part_time"

terms = document.get_field_by_name("AcceptTerms")
if terms is not None:
    terms.value = True
```

Because `PDFRepresentation` uses assignment validation, invalid replacements in
`document.fields` or `document.rows` will be checked as well.

## Example: Validation Errors

The models reject inconsistent field definitions early:

```python
from pydantic import ValidationError
from pdf_schema import PDFField

try:
    PDFField(
        id="bad-1",
        name="BadCheckbox",
        type="checkbox",
        value="yes",  # invalid: checkbox values must be bool
    )
except ValidationError as exc:
    print(exc)
```

Another common error is attaching `choices` to a text field or using
`textarea_rows` on a non-`textarea` field.

## Example: JSON Round-trip

You can validate incoming JSON by parsing it back into the model:

```python
json_text = document.model_dump_json(indent=2)
restored = PDFRepresentation.model_validate_json(json_text)

assert restored.get_field_by_name("EmploymentType") is not None
assert restored.spec_version == "1.0"
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
