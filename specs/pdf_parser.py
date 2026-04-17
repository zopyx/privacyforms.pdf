#!/usr/bin/env python3
"""Parse a fillable PDF form into the PDFRepresentation schema."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from collections.abc import Sequence

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, NameObject

try:
    from .pdf_schema import (
        ChoiceOption,
        FieldFlags,
        FieldLayout,
        PDFField,
        PDFFieldType,
        PDFRepresentation,
        RowGroup,
    )
except ImportError:
    from pdf_schema import (
        ChoiceOption,
        FieldFlags,
        FieldLayout,
        PDFField,
        PDFFieldType,
        PDFRepresentation,
        RowGroup,
    )

# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

@dataclass
class _RawFieldInfo:
    """Temporary container for extracted field data before model construction."""

    name: str
    pdf_type: str  # /Tx, /Btn, /Sig, /Ch
    flags: int | None
    value: object = None
    default_value: object = None
    kids: ArrayObject | None = None
    rect: list[float] | None = None
    page_index: int = 0
    opts: list[object] | None = None
    max_length: int | None = None


# PDF field flag bit masks (0-indexed bits matching PDF spec 1-indexed positions)
_READ_ONLY = 1 << 0
_REQUIRED = 1 << 1
_NO_EXPORT = 1 << 2

_NO_TOGGLE_TO_OFF = 1 << 14
_RADIO = 1 << 15
_PUSHBUTTON = 1 << 16

_MULTILINE = 1 << 12
_PASSWORD = 1 << 13
_FILE_SELECT = 1 << 20
_DO_NOT_SPELLCHECK = 1 << 22
_DO_NOT_SCROLL = 1 << 23
_COMB = 1 << 24
_RICH_TEXT = 1 << 25

_COMBO = 1 << 17
_EDIT = 1 << 18
_SORT = 1 << 19
_MULTI_SELECT = 1 << 21
_COMMIT_ON_SEL_CHANGE = 1 << 26


def _parse_field_flags(raw: int | None) -> FieldFlags:
    """Build FieldFlags from raw PDF /Ff integer."""
    if raw is None:
        raw = 0
    return FieldFlags(
        read_only=bool(raw & _READ_ONLY),
        required=bool(raw & _REQUIRED),
        no_export=bool(raw & _NO_EXPORT),
        no_toggle_to_off=bool(raw & _NO_TOGGLE_TO_OFF),
        radio=bool(raw & _RADIO),
        pushbutton=bool(raw & _PUSHBUTTON),
        multiline=bool(raw & _MULTILINE),
        password=bool(raw & _PASSWORD),
        file_select=bool(raw & _FILE_SELECT),
        do_not_spellcheck=bool(raw & _DO_NOT_SPELLCHECK),
        do_not_scroll=bool(raw & _DO_NOT_SCROLL),
        comb=bool(raw & _COMB),
        rich_text=bool(raw & _RICH_TEXT),
        combo=bool(raw & _COMBO),
        edit=bool(raw & _EDIT),
        sort=bool(raw & _SORT),
        multi_select=bool(raw & _MULTI_SELECT),
        commit_on_sel_change=bool(raw & _COMMIT_ON_SEL_CHANGE),
    )


def _is_date_field(name: str, value: str | None) -> bool:
    """Heuristic to detect date fields from name and value patterns."""
    date_keywords = [
        "date", "start date", "end date", "dob", "birth", "hired",
    ]
    lower_name = name.lower()
    if any(kw in lower_name for kw in date_keywords):
        return True
    if value and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return True
    if value and re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", value):
        return True
    return False


def _strip_pdf_string(value: object) -> str | None:
    """Normalize a PDF string value: remove leading/trailing parentheses if present."""
    if value is None:
        return None
    text = str(value)
    # pypdf NameObject values like /Yes appear as 'Yes' or '/Yes'
    if text.startswith("/"):
        text = text[1:]
    if text == "Off":
        return "Off"
    return text.strip() or None


def _normalize_value(value: object) -> str | bool | list[str] | None:
    """Convert a raw PDF value to a Python scalar."""
    if value is None:
        return None
    if isinstance(value, NameObject):
        text = str(value)
        if text.startswith("/"):
            text = text[1:]
        if text == "Yes" or text == "On":
            return True
        if text == "Off" or text == "No":
            return False
        return text or None
    if isinstance(value, str):
        return value.strip() or None
    return str(value).strip() or None


def _get_appearance_states(widget_dict: DictionaryObject) -> list[str]:
    """Extract on-state names from a widget's appearance dictionary."""
    states: set[str] = set()
    ap = widget_dict.get("/AP")
    if not ap:
        return []
    apo = ap.get_object() if hasattr(ap, "get_object") else ap
    if not isinstance(apo, DictionaryObject):
        return []
    n = apo.get("/N")
    if not n:
        return []
    no = n.get_object() if hasattr(n, "get_object") else n
    if not isinstance(no, DictionaryObject):
        return []
    for key in no.keys():
        key_str = str(key)
        if key_str.startswith("/"):
            key_str = key_str[1:]
        if key_str != "Off":
            states.add(key_str)
    return sorted(states)


def _extract_choices_for_button(field_dict: DictionaryObject) -> list[ChoiceOption]:
    """Build ChoiceOption list for button fields (radio/checkbox) from kid widgets."""
    kids = field_dict.get("/Kids")
    if not isinstance(kids, ArrayObject):
        # Single widget: try to get states from the field itself
        states = _get_appearance_states(field_dict)
        if not states:
            # Fallback: inspect /V and common states
            val = field_dict.get("/V")
            if val is not None:
                val_str = str(val)
                if val_str.startswith("/"):
                    val_str = val_str[1:]
                if val_str != "Off":
                    states = [val_str]
            if not states:
                states = ["Yes"]
        return [ChoiceOption(value=s, text=s, source_name=s) for s in states]

    all_states: list[str] = []
    for kid in kids:
        ko = kid.get_object() if hasattr(kid, "get_object") else kid
        if isinstance(ko, DictionaryObject):
            states = _get_appearance_states(ko)
            all_states.extend(states)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_states: list[str] = []
    for s in all_states:
        if s not in seen:
            seen.add(s)
            unique_states.append(s)

    if not unique_states:
        unique_states = ["Yes"]

    return [ChoiceOption(value=s, text=s, source_name=s) for s in unique_states]


def _extract_choices_for_choice(field_dict: DictionaryObject) -> list[ChoiceOption]:
    """Build ChoiceOption list for choice fields (/Ch) from /Opt array."""
    opts = field_dict.get("/Opt")
    if not opts:
        return []

    choices: list[ChoiceOption] = []
    opt_array = opts.get_object() if hasattr(opts, "get_object") else opts
    if not isinstance(opt_array, ArrayObject):
        return []

    for item in opt_array:
        if isinstance(item, ArrayObject) and len(item) >= 2:
            # [export_value, display_text]
            export_val = str(item[0])
            display = str(item[1])
        else:
            export_val = str(item)
            display = export_val

        # Strip leading slash from NameObjects
        if export_val.startswith("/"):
            export_val = export_val[1:]
        if display.startswith("/"):
            display = display[1:]

        choices.append(
            ChoiceOption(
                value=export_val.strip() or export_val,
                text=display.strip() or None,
                source_name=export_val.strip() or None,
            )
        )
    return choices


def _determine_button_type(field_flags: FieldFlags, num_kids: int) -> PDFFieldType:
    """Classify a /Btn field as checkbox or radiobuttongroup."""
    if field_flags.pushbutton:
        # Unsupported in our schema; treat as checkbox as a fallback
        return "checkbox"
    if field_flags.radio or num_kids > 1:
        return "radiobuttongroup"
    return "checkbox"


def _determine_text_type(name: str, value: str | None, field_flags: FieldFlags) -> PDFFieldType:
    """Classify a /Tx field as textfield, textarea, or datefield."""
    if field_flags.multiline:
        return "textarea"
    if _is_date_field(name, value):
        return "datefield"
    return "textfield"


def _determine_choice_type(field_flags: FieldFlags) -> PDFFieldType:
    """Classify a /Ch field as combobox or listbox."""
    if field_flags.combo:
        return "combobox"
    return "listbox"


def _bbox_for_kids(kids: ArrayObject) -> list[float] | None:
    """Compute the bounding box that contains all kid widgets."""
    rects: list[list[float]] = []
    for kid in kids:
        ko = kid.get_object() if hasattr(kid, "get_object") else kid
        if isinstance(ko, DictionaryObject):
            rect = ko.get("/Rect")
            if rect and len(rect) == 4:
                rects.append([float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])])
    if not rects:
        return None
    xs = [r[0] for r in rects] + [r[2] for r in rects]
    ys = [r[1] for r in rects] + [r[3] for r in rects]
    return [min(xs), min(ys), max(xs), max(ys)]


def _build_layout(
    page_index: int | None,
    rect: list[float] | None,
) -> FieldLayout | None:
    """Build FieldLayout from raw rectangle."""
    if rect is None or len(rect) != 4:
        return None
    x1, y1, x2, y2 = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    return FieldLayout(
        page=page_index,
        x=int(min(x1, x2)),
        y=int(min(y1, y2)),
        width=int(abs(x2 - x1)),
        height=int(abs(y2 - y1)),
    )


def _collect_annotation_info(
    pdf_path: Path | str,
) -> tuple[dict[str, tuple[int, list[float] | None]], dict[tuple[int, int], tuple[int, list[float] | None]]]:
    """Map widget annotations by field name and by indirect reference.

    Returns:
        A tuple of (name_map, ref_map) where ref_map uses (idnum, generation) as key.
    """
    reader = PdfReader(str(pdf_path))
    name_map: dict[str, tuple[int, list[float] | None]] = {}
    ref_map: dict[tuple[int, int], tuple[int, list[float] | None]] = {}
    for page_idx, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        for annot in annots:
            ao = annot.get_object() if hasattr(annot, "get_object") else annot
            if not isinstance(ao, DictionaryObject):
                continue
            if ao.get("/Subtype") != "/Widget":
                continue
            rect = ao.get("/Rect")
            ref_key = (annot.idnum, annot.generation)
            ref_map[ref_key] = (page_idx + 1, rect)
            t = ao.get("/T")
            if t:
                name = str(t)
                if name not in name_map:
                    name_map[name] = (page_idx + 1, rect)
    return name_map, ref_map


def extract_pdf_form(pdf_filename: Path | str) -> PDFRepresentation:
    """Extract PDF form data into the PDFRepresentation schema.

    This is a public facade that parses a fillable PDF and returns a
    Pydantic-validated PDFRepresentation object.

    Args:
        pdf_filename: Path to the PDF file to parse.

    Returns:
        PDFRepresentation containing all extracted fields, layout, and rows.
    """
    return parse_pdf(Path(pdf_filename))


def parse_pdf(pdf_path: Path | str, source: str | None = None) -> PDFRepresentation:
    """Parse a PDF form into PDFRepresentation.

    Args:
        pdf_path: Path to the PDF file.
        source: Optional source identifier for the document.

    Returns:
        PDFRepresentation model populated from the PDF.
    """
    pdf_path = Path(pdf_path)
    reader = PdfReader(str(pdf_path))
    fields = reader.get_fields()
    annot_info, ref_map = _collect_annotation_info(pdf_path)

    pdf_fields: list[PDFField] = []
    field_layouts: dict[str, FieldLayout] = {}

    if not fields:
        return PDFRepresentation(source=source or str(pdf_path))

    for idx, (name, field_ref) in enumerate(fields.items()):
        field_dict = field_ref.get_object() if hasattr(field_ref, "get_object") else field_ref
        if not isinstance(field_dict, DictionaryObject):
            continue

        pdf_type = str(field_dict.get("/FT", ""))
        raw_flags = field_dict.get("/Ff")
        flags_int = int(raw_flags) if raw_flags is not None else None
        field_flags = _parse_field_flags(flags_int)

        raw_value = field_dict.get("/V")
        raw_default = field_dict.get("/DV")
        kids = field_dict.get("/Kids")
        num_kids = len(kids) if isinstance(kids, ArrayObject) else 0

        # Determine normalized type
        field_type: PDFFieldType
        if pdf_type == "/Tx":
            stripped_value = _strip_pdf_string(raw_value)
            field_type = _determine_text_type(name, stripped_value, field_flags)
        elif pdf_type == "/Btn":
            field_type = _determine_button_type(field_flags, num_kids)
        elif pdf_type == "/Sig":
            field_type = "signature"
        elif pdf_type == "/Ch":
            field_type = _determine_choice_type(field_flags)
        else:
            # Skip unsupported types (pushbutton, barcode, etc.)
            continue

        # Normalize values according to type
        if field_type == "checkbox":
            value = _normalize_value(raw_value)
            default_value = _normalize_value(raw_default)
            # Ensure bool type
            if isinstance(value, str):
                value = value not in {"Off", "No", "False", ""}
            if isinstance(default_value, str):
                default_value = default_value not in {"Off", "No", "False", ""}
        elif field_type == "radiobuttongroup":
            value = _strip_pdf_string(raw_value)
            default_value = _strip_pdf_string(raw_default)
            if value == "Off":
                value = None
            if default_value == "Off":
                default_value = None
        elif field_type in {"textfield", "textarea", "datefield", "signature"}:
            value = _strip_pdf_string(raw_value)
            default_value = _strip_pdf_string(raw_default)
        elif field_type in {"combobox", "listbox"}:
            if field_flags.multi_select and isinstance(raw_value, ArrayObject):
                value = [_strip_pdf_string(v) for v in raw_value if _strip_pdf_string(v) is not None]
            else:
                value = _strip_pdf_string(raw_value)
            default_value = _strip_pdf_string(raw_default)
        else:
            value = _strip_pdf_string(raw_value)
            default_value = _strip_pdf_string(raw_default)

        # Choices
        choices: list[ChoiceOption] = []
        if field_type == "radiobuttongroup":
            choices = _extract_choices_for_button(field_dict)
        elif field_type in {"combobox", "listbox"}:
            choices = _extract_choices_for_choice(field_dict)

        # Layout resolution
        page_index, rect = annot_info.get(name, (None, None))
        if (page_index is None or rect is None) and num_kids > 0:
            kid_rects: list[list[float]] = []
            kid_pages: list[int] = []
            for kid in kids:
                ref_key = (kid.idnum, kid.generation)
                if ref_key in ref_map:
                    p_idx, k_rect = ref_map[ref_key]
                    kid_pages.append(p_idx)
                    if k_rect:
                        kid_rects.append([float(k_rect[0]), float(k_rect[1]), float(k_rect[2]), float(k_rect[3])])
            if kid_pages:
                page_index = kid_pages[0]
            if kid_rects:
                xs = [r[0] for r in kid_rects] + [r[2] for r in kid_rects]
                ys = [r[1] for r in kid_rects] + [r[3] for r in kid_rects]
                rect = [min(xs), min(ys), max(xs), max(ys)]
        layout = _build_layout(page_index, rect)

        # Max length
        max_len = field_dict.get("/MaxLen")
        max_length = int(max_len) if max_len is not None else None

        # Generate a stable id
        field_id = f"f-{idx}"

        # Omit field_flags entirely when no flags are set
        effective_flags = field_flags if flags_int is not None else None
        if effective_flags is not None and not effective_flags.model_dump():
            effective_flags = None

        # Build PDFField
        pdf_field = PDFField(
            name=name,
            id=field_id,
            type=field_type,
            title=None,
            field_flags=effective_flags,
            layout=layout,
            default_value=default_value,
            value=value,
            choices=choices,
            format=None,  # Could be enhanced with format heuristics
            max_length=max_length,
            textarea_rows=None,
            textarea_cols=None,
        )
        pdf_fields.append(pdf_field)
        if layout is not None:
            field_layouts[field_id] = layout

    # Row grouping heuristic: cluster by page and y-coordinate
    rows = _build_rows(pdf_fields)

    return PDFRepresentation(
        source=source or str(pdf_path),
        fields=pdf_fields,
        rows=rows,
    )


def _build_rows(fields: Sequence[PDFField], y_tolerance: int = 15) -> list[RowGroup]:
    """Group fields into visual rows based on layout proximity."""
    # Group by page
    page_fields: dict[int, list[PDFField]] = {}
    for f in fields:
        if f.layout is None or f.layout.page is None:
            continue
        page_fields.setdefault(f.layout.page, []).append(f)

    rows: list[RowGroup] = []
    for page_idx in sorted(page_fields.keys()):
        pf = page_fields[page_idx]
        # Sort by y descending (top of page first)
        pf.sort(key=lambda f: -(f.layout.y if f.layout else 0))

        current_row: list[PDFField] = []
        current_y: int | None = None
        for f in pf:
            fy = f.layout.y if f.layout else 0
            if current_y is None:
                current_row = [f]
                current_y = fy
            elif abs(fy - current_y) <= y_tolerance:
                current_row.append(f)
            else:
                # Sort row by x ascending
                current_row.sort(key=lambda fld: fld.layout.x if fld.layout else 0)
                rows.append(RowGroup(fields=current_row, page_index=page_idx))
                current_row = [f]
                current_y = fy
        if current_row:
            current_row.sort(key=lambda fld: fld.layout.x if fld.layout else 0)
            rows.append(RowGroup(fields=current_row, page_index=page_idx))

    return rows


def _print_rows(representation: PDFRepresentation, *, show_ids: bool = False) -> None:
    """Print a compact, human-readable overview of row groups and fields."""
    click.echo(f"\nParsed {len(representation.fields)} fields into {len(representation.rows)} rows\n")
    for idx, row in enumerate(representation.rows, start=1):
        labels = [field.id if show_ids else field.name for field in row.fields]
        click.echo(f"Row {idx:2d} (page {row.page_index}): {', '.join(labels)}")


@click.command()
@click.argument("pdf_file", type=click.Path(exists=True, path_type=Path))
@click.argument("output_json", required=False, type=click.Path(path_type=Path))
@click.option(
    "--by-id",
    "by_id",
    is_flag=True,
    default=False,
    help="Display rows using field IDs instead of field names.",
)
def main(pdf_file: Path, output_json: Path | None, by_id: bool) -> None:
    """Parse PDF_FILE into JSON and write it to OUTPUT_JSON (default: <pdf-stem>.json)."""
    output_path = output_json if output_json is not None else pdf_file.with_suffix(".json")

    representation = parse_pdf(pdf_file)
    json_text = representation.to_compact_json(indent=2)

    output_path.write_text(json_text, encoding="utf-8")
    click.echo(f"Written to {output_path}")
    _print_rows(representation, show_ids=by_id)


if __name__ == "__main__":
    main()
