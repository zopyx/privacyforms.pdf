# Suggestions for Modernizing `pdf_schema.py`

This document lists recommendations to make `pdf_schema.py` a complete, specification-grade representation of **all possible PDF form field types** per ISO 32000. The analysis is based on the current extractor logic (`privacyforms_pdf/reader.py`, `privacyforms_pdf/models.py`, `privacyforms_pdf/filler.py`), pypdf capabilities, and the PDF specification.

---

## 1. Missing Field Types

The current `type: str` is too loose and omits field types the extractor does not yet surface.

| PDF `/FT` | Flag condition | Suggested `type` value | Status in codebase |
|-----------|----------------|------------------------|-------------------|
| `/Tx` | — | `textfield` | ✅ handled |
| `/Tx` | `/AA` or `/DV` heuristic | `datefield` | ⚠️ heuristic, fragile |
| `/Btn` | no `/Opt`, no pushbutton flag | `checkbox` | ✅ handled |
| `/Btn` | `/Opt` present | `radiobuttongroup` | ✅ handled |
| `/Btn` | `Ff` bit 17 set (pushbutton) | **`pushbutton`** | ❌ **missing** |
| `/Ch` | `Ff` bit 18 set | `combobox` | ✅ handled |
| `/Ch` | — | `listbox` | ✅ handled |
| `/Sig` | — | `signature` | ✅ handled |
| `/Barcode` | PDF 2.0 | **`barcode`** | ❌ **missing** |

**Recommendations:**
- Change `type` from `str` to a `Literal` or `Enum` containing all known types.
- Add `pushbutton` and `barcode` so the schema is future-proof.
- Fix `datefield` detection in `reader.py` (see section 6).

---

## 2. Missing Core Identity Fields

`pdf_schema.py` is missing several fields that exist on every real PDF field and are present in `models.py`:

| Field | PDF key | Why it matters |
|-------|---------|---------------|
| **`name`** | `/T` | The field’s partial name. Required for filling. |
| **`pages`** | derived from widgets | A field can have widgets on multiple pages. |
| **`locked`** / **`read_only`** | `Ff` bit 1 | Currently missing from the spec file. |
| **`required`** | `Ff` bit 2 | Validation-critical metadata. |
| **`field_flags`** | `/Ff` integer | Expose the raw bitfield so clients can inspect multiline, password, fileSelect, doNotSpellCheck, comb, richText, multiSelect, etc. without guessing. |

**Recommendations:**
- Add `name: str`, `pages: list[int]`, `read_only: bool`, `required: bool`, and `field_flags: int | None`.

---

## 3. Value Representation is Inconsistent

You currently have both `default_value: object | None` and `values: list[str]`. This is problematic:

- `object` is too broad for Pydantic validation.
- `values: list[str]` implies multi-value, but for 99% of fields (textfield, checkbox, signature) PDFs store a **single** value (`/V`).
- Only multi-select listboxes legitimately have multiple values (`/V` can be an array).

**Recommendations:**
- Replace `values: list[str]` with `value: str | bool | list[str] | None` (union type).
- Change `default_value` to `str | bool | list[str] | None` as well.
- Add **`selected_indices: list[int] | None`** to capture `/I` for multi-select listboxes.
- Add **`top_index: int | None`** to capture `/TI` (listbox scroll position).

---

## 4. Geometry Should be a Nested Model

Flattening geometry into `visual_x`, `visual_y`, `visual_width`, `visual_height` (all `int | None`) loses critical information:

- PDF coordinates are **floats**, not ints.
- You lose the **page number** (fields can span pages).
- You lose the raw `rect` tuple, which is needed for accurate rendering.
- The main `models.py` already uses a nested `FieldGeometry` model.

**Recommendations:**
- Replace the four flat `visual_*` fields with a nested `geometry` model:

```python
class FieldGeometry(BaseModel):
    page: int                      # 1-based page number
    rect: tuple[float, float, float, float]
    x: float
    y: float
    width: float
    height: float
    units: Literal["pt"] = "pt"
```

This aligns `pdf_schema.py` with `models.py` and with the PDF spec.

---

## 5. Missing Field-Specific Properties

Several PDF keys are common in real-world forms but absent from the schema:

| Property | PDF key | Applies to | Use case |
|----------|---------|------------|----------|
| **`format`** | heuristic (`/AA`, `/DV`) or `/FT` == `/Tx` + `Ff` | datefield | Date format string. Already in `models.py`, missing in spec. |
| **`max_length`** | `/MaxLen` | textfield | Present ✅ |
| **`tooltip`** | `/TU` | all fields | Accessibility / screen-reader text. |
| **`mapping_name`** | `/TM` | all fields | Export name for XML data binding. |
| **`alignment`** | `/Q` | textfield | Text alignment: `0=left`, `1=center`, `2=right`. |
| **`default_appearance`** | `/DA` | textfield, choice | Font name, size, and color string (e.g. `/Helv 12 Tf 0 g`). |
| **`multiline`** | `Ff` bit 13 | textfield | Distinguish `textarea` from single-line text. |
| **`password`** | `Ff` bit 14 | textfield | Masked input field. |
| **`file_select`** | `Ff` bit 21 | textfield | File path selector. |
| **`comb`** | `Ff` bit 25 | textfield | Comb-style spacing (e.g. SSN fields). |
| **`rich_text`** | `Ff` bit 26 | textfield | Supports rich text (`/RV`, `/DS`). |
| **`multi_select`** | `Ff` bit 22 | choice (`/Ch`) | Allows multiple selections in listbox. |
| **`action`** | `/A` | pushbutton | The action dictionary (URI, JavaScript, etc.). |
| **`appearance_characteristics`** | `/MK` | button, choice | Background color, border, caption (`/CA`, `/RC`, `/AC`). |

**Recommendations:**
- Add the above properties. At minimum, expose `tooltip`, `alignment`, `multiline`, `password`, `multi_select`, `action`, and `appearance_characteristics`.

---

## 6. `datefield` Detection is Fragile

In `reader.py`, `datefield` is detected by:

```python
if "/AA" in field or "/DV" in field:
    return "datefield"
```

This is **wrong** for many PDFs:
- `/DV` (default value) exists on regular text fields.
- `/AA` (additional actions) exists on many non-date fields for JavaScript formatting.

**Better heuristics:**
1. Check if `/FT` is `/Tx` **and** the field flags include the **commit-on-sel-change** or other date-specific patterns.
2. Parse `/DV` or `/V` against common PDF date patterns (`D:YYYYMMDD`, `mm/dd/yyyy`, etc.).
3. Check the **JavaScript action** (`/AA` `/Fo` or `/K`) for date-related format scripts.

**Recommendations:**
- Move the heuristic out of `get_field_type()` or improve it.
- In `pdf_schema.py`, keep `datefield` as a valid type but add `format: str | None` so the consumer can at least see the intended format string.

---

## 7. Textarea Ambiguity

The current schema has `textarea_rows` and `textarea_cols`, but the `type` does not include `textarea`. In the PDF spec, a textarea is just a `/Tx` field with the **multiline flag** (`Ff` bit 13) set.

**Recommendations:**
- Either add `textarea` as a distinct `type` value (when multiline is detected), **or**
- Keep `type == "textfield"` and rely on `multiline: bool` + `textarea_rows` / `textarea_cols`.
- The latter is more spec-accurate, but if the goal is UI-friendly types, add `textarea` to the `Literal`/`Enum`.

---

## 8. Type Safety Improvements

- **`type` → `Literal`** or `StrEnum` instead of plain `str`.
- **`value` and `default_value`** → `str | bool | list[str] | None` instead of `object`.
- **`values` → remove** (redundant with `value`).

---

## Summary of Recommended Additions to `PDFField`

### New fields to add
- `name: str`
- `pages: list[int]`
- `read_only: bool`
- `required: bool`
- `field_flags: int | None`
- `value: str | bool | list[str] | None` (replace `values`)
- `format: str | None`
- `tooltip: str | None`
- `mapping_name: str | None`
- `alignment: Literal[0, 1, 2] | None`
- `default_appearance: str | None`
- `multiline: bool`
- `password: bool`
- `file_select: bool`
- `comb: bool`
- `rich_text: bool`
- `multi_select: bool`
- `selected_indices: list[int] | None`
- `top_index: int | None`
- `action: dict[str, Any] | None`
- `appearance_characteristics: dict[str, Any] | None`

### Fields to modify
- `type: Literal["textfield", "textarea", "datefield", "checkbox", "radiobuttongroup", "combobox", "listbox", "signature", "pushbutton", "barcode"]`
- Replace `visual_x/y/width/height` with nested `geometry: FieldGeometry | None`
- Replace `values: list[str]` with `value: str | bool | list[str] | None`
- Change `default_value` from `object` to `str | bool | list[str] | None`

### Fields to remove
- `values` (the list variant) — unless it is needed for a different semantic purpose than `value`.
