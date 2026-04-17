#!/usr/bin/env python3
"""Parse a fillable PDF form into the PDFRepresentation schema."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, NameObject

from .schema import (
    ChoiceOption,
    FieldFlags,
    PDFField,
    PDFFieldType,
    PDFRepresentation,
)
from .schema_layout import _build_layout, _build_rows

# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

_MAX_PDF_SIZE = 50 * 1024 * 1024  # 50 MB
_MAX_FIELDS = 10_000


def _check_input_size(path: Path, max_size: int = _MAX_PDF_SIZE) -> None:
    """Raise ValueError if *path* exists and exceeds *max_size* bytes."""
    if not path.exists():
        return
    size = path.stat().st_size
    if size > max_size:
        raise ValueError(
            f"Input file too large: {path.name} ({size} bytes). "
            f"Maximum allowed is {max_size} bytes."
        )


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


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


# Common English keywords that indicate a field stores a date.
# This is a heuristic because PDF text fields do not declare a date subtype;
# authors typically encode intent in the field name.
_DATE_KEYWORDS_RE = re.compile(r"\b(date|dob|birth|hired)\b", re.IGNORECASE)


def _is_date_field(name: str, value: str | None) -> bool:
    """Heuristic to detect date fields from name and value patterns.

    PDF does not have a dedicated "date" field type; dates are stored in
    standard text fields (/Tx). We infer the intent from:

    1. Field name: presence of keywords such as "date", "dob", "birth",
       "hired" (case-insensitive).
    2. Current value: common date formats (ISO 8601 yyyy-mm-dd or regional
       d/m/yyyy, mm/dd/yy, etc.).

    False positives are possible (e.g. a field named "candidate" containing
    "01/01/2025"), but the heuristic errs on the side of labelling a text
    field as datefield, which is harmless for downstream conversion.
    """
    lower_name = name.lower()
    if _DATE_KEYWORDS_RE.search(lower_name):
        return True
    return bool(
        value
        and (
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
            or re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", value)
        )
    )


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
    for key in no:
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


def determine_button_type(
    field_flags: FieldFlags, num_kids: int, has_opt: bool = False
) -> PDFFieldType:
    """Classify a /Btn field as checkbox or radiobuttongroup."""
    if field_flags.radio or num_kids > 1 or has_opt:
        return "radiobuttongroup"
    return "checkbox"


def determine_text_type(name: str, value: str | None, field_flags: FieldFlags) -> PDFFieldType:
    """Classify a /Tx field as textfield, textarea, or datefield."""
    if field_flags.multiline:
        return "textarea"
    if _is_date_field(name, value):
        return "datefield"
    return "textfield"


def determine_choice_type(field_flags: FieldFlags) -> PDFFieldType:
    """Classify a /Ch field as combobox or listbox."""
    if field_flags.combo:
        return "combobox"
    return "listbox"


def get_field_type(field: dict[str, Any]) -> str:
    """Determine field type from a pypdf field dictionary.

    This is a standalone helper for consumers (e.g. FormFiller) that
    need to classify a field given only the raw pypdf data.
    It follows the legacy detection rules for backwards compatibility.

    Args:
        field: Field dictionary from pypdf.

    Returns:
        Field type string.
    """
    ft = field.get("/FT")
    if ft is None:
        ft = field.get("/Type")

    if ft == "/Tx":
        raw_flags = field.get("/Ff")
        flags_int = int(raw_flags) if raw_flags is not None else None
        field_flags = _parse_field_flags(flags_int)
        if field_flags.multiline:
            return "textarea"
        return "textfield"
    elif ft == "/Btn":
        if "/Opt" in field:
            return "radiobuttongroup"
        return "checkbox"
    elif ft == "/Ch":
        ff = field.get("/Ff", 0)
        if isinstance(ff, int) and ff & 0x40000:
            return "combobox"
        return "listbox"
    elif ft == "/Sig":
        return "signature"

    return "textfield"


def get_field_options(field: dict[str, Any]) -> list[str]:
    """Extract options for choice/radio fields from a pypdf field dictionary.

    Args:
        field: Field dictionary from pypdf.

    Returns:
        List of option strings.
    """
    opts = field.get("/Opt")
    if opts:
        result: list[str] = []
        opt_array = opts.get_object() if hasattr(opts, "get_object") else opts
        if isinstance(opt_array, (ArrayObject, list)):
            for opt in opt_array:
                if isinstance(opt, (ArrayObject, list)) and len(opt) >= 2:
                    result.append(str(opt[1]))
                elif isinstance(opt, (ArrayObject, list)) and len(opt) == 1:
                    result.append(str(opt[0]))
                else:
                    result.append(str(opt))
        return result

    kids = field.get("/Kids", [])
    if kids:
        opt_list: list[str] = []
        for kid in kids:
            kid_obj = kid.get_object() if hasattr(kid, "get_object") else kid
            if kid_obj and "/AP" in kid_obj:
                ap = kid_obj["/AP"]
                if "/N" in ap:
                    names = list(ap["/N"].keys())
                    opt_list.extend([str(n) for n in names if str(n).lower() != "/off"])
        return list(dict.fromkeys(opt_list))

    return []


def _collect_annotation_info(
    reader: PdfReader,
) -> tuple[
    dict[str, tuple[int, list[float] | None]], dict[tuple[int, int], tuple[int, list[float] | None]]
]:
    """Map widget annotations by field name and by indirect reference.

    Returns:
        A tuple of (name_map, ref_map) where ref_map uses (idnum, generation) as key.
    """
    name_map: dict[str, tuple[int, list[float] | None]] = {}
    ref_map: dict[tuple[int, int], tuple[int, list[float] | None]] = {}
    for page_idx, page in enumerate(getattr(reader, "pages", ())):
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
            if hasattr(annot, "idnum") and hasattr(annot, "generation"):
                ref_key = (annot.idnum, annot.generation)
                ref_map[ref_key] = (page_idx + 1, rect)
            t = ao.get("/T")
            if t:
                name = str(t)
                if name not in name_map:
                    name_map[name] = (page_idx + 1, rect)
    return name_map, ref_map


def _resolve_source(pdf_path: Path, source: str | None) -> str:
    """Return the source identifier used in the parsed representation."""
    return source or pdf_path.name


def _resolve_kid_layout(
    kids: ArrayObject,
    ref_map: dict[tuple[int, int], tuple[int, list[float] | None]],
) -> tuple[int | None, list[float] | None]:
    """Resolve page index and combined widget rect from kid annotations."""
    kid_rects: list[list[float]] = []
    kid_pages: list[int] = []
    for kid in kids:
        if hasattr(kid, "idnum") and hasattr(kid, "generation"):
            ref_key = (kid.idnum, kid.generation)
            if ref_key in ref_map:
                page_index, rect = ref_map[ref_key]
                kid_pages.append(page_index)
                if rect and len(rect) == 4:
                    kid_rects.append(
                        [float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])]
                    )
                continue

        ko = kid.get_object() if hasattr(kid, "get_object") else kid
        if not isinstance(ko, DictionaryObject):
            continue
        rect = ko.get("/Rect")
        if rect and len(rect) == 4:
            kid_rects.append([float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])])

    page_index = kid_pages[0] if kid_pages else None
    if not kid_rects:
        return page_index, None

    xs = [r[0] for r in kid_rects] + [r[2] for r in kid_rects]
    ys = [r[1] for r in kid_rects] + [r[3] for r in kid_rects]
    return page_index, [min(xs), min(ys), max(xs), max(ys)]


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


def parse_pdf(
    pdf_path: Path | str,
    source: str | None = None,
    reader: PdfReader | None = None,
) -> PDFRepresentation:
    """Parse a PDF form into PDFRepresentation.

    Args:
        pdf_path: Path to the PDF file.
        source: Optional source identifier for the document.
        reader: Optional pre-existing PdfReader instance.

    Returns:
        PDFRepresentation model populated from the PDF.

    Raises:
        ValueError: If the PDF contains too many fields (>10,000).
    """
    pdf_path = Path(pdf_path)
    _check_input_size(pdf_path)
    if reader is None:
        reader = PdfReader(str(pdf_path))
    fields = reader.get_fields()
    annot_info, ref_map = _collect_annotation_info(reader)
    resolved_source = _resolve_source(pdf_path, source)

    pdf_fields: list[PDFField] = []

    if not fields:
        return PDFRepresentation(source=resolved_source)

    if len(fields) > _MAX_FIELDS:
        raise ValueError(
            f"PDF contains too many fields: {len(fields)}. Maximum allowed is {_MAX_FIELDS}."
        )

    for name, field_ref in fields.items():
        field_dict = field_ref.get_object() if hasattr(field_ref, "get_object") else field_ref
        if not isinstance(field_dict, (DictionaryObject, dict)):
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
            field_type = determine_text_type(name, stripped_value, field_flags)
        elif pdf_type == "/Btn":
            if field_flags.pushbutton:
                continue
            has_opt = "/Opt" in field_dict
            field_type = determine_button_type(field_flags, num_kids, has_opt=has_opt)
        elif pdf_type == "/Sig":
            field_type = "signature"
        elif pdf_type == "/Ch":
            field_type = determine_choice_type(field_flags)
        else:
            # Skip unsupported types (pushbutton, barcode, etc.)
            continue

        # Normalize values according to type
        if field_type == "checkbox":
            value = _normalize_value(raw_value)
            default_value = _normalize_value(raw_default)
            # Ensure bool type (case-insensitive)
            if isinstance(value, str):
                value = value.strip().lower() not in {"off", "no", "false", ""}
            if isinstance(default_value, str):
                default_value = default_value.strip().lower() not in {"off", "no", "false", ""}
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
                raw_list = [_strip_pdf_string(v) for v in raw_value]
                value = [v for v in raw_list if v is not None]
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
            page_index, rect = _resolve_kid_layout(kids, ref_map)
        layout = _build_layout(page_index, rect)

        # Max length
        max_len = field_dict.get("/MaxLen")
        max_length = int(max_len) if max_len is not None else None

        # Generate a stable id
        field_id = f"f-{len(pdf_fields)}"

        # Omit field_flags entirely when no flags are set
        effective_flags = field_flags if flags_int is not None else None
        if effective_flags is not None and flags_int == 0:
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

    # Row grouping heuristic: cluster by page and y-coordinate
    rows = _build_rows(pdf_fields)

    return PDFRepresentation(
        source=resolved_source,
        fields=pdf_fields,
        rows=rows,
    )
