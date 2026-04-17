from typing import Literal

from pydantic import BaseModel, Field

PDFFieldType = Literal[
    "textfield",
    "textarea",
    "datefield",
    "checkbox",
    "radiobuttongroup",
    "combobox",
    "listbox",
    "signature",
]


class FieldFlags(BaseModel):
    """Human-readable PDF field flags parsed from /Ff integer."""

    read_only: bool = Field(
        default=False,
        description="Field is read-only (bit 1).",
    )
    required: bool = Field(
        default=False,
        description="Field is required (bit 2).",
    )
    no_export: bool = Field(
        default=False,
        description="Field value must not be exported (bit 3).",
    )

    no_toggle_to_off: bool = Field(
        default=False,
        description="Radio button group: no toggling to off (bit 15).",
    )
    radio: bool = Field(
        default=False,
        description="Button field behaves as a radio (bit 16).",
    )
    pushbutton: bool = Field(
        default=False,
        description="Button field is a pushbutton (bit 17).",
    )

    multiline: bool = Field(
        default=False,
        description="Text field supports multiple lines (bit 13).",
    )
    password: bool = Field(
        default=False,
        description="Text field is a password input (bit 14).",
    )
    file_select: bool = Field(
        default=False,
        description="Text field is a file selection control (bit 21).",
    )
    do_not_spellcheck: bool = Field(
        default=False,
        description="Do not spell-check the field (bit 23).",
    )
    do_not_scroll: bool = Field(
        default=False,
        description="Text field does not scroll (bit 24).",
    )
    comb: bool = Field(
        default=False,
        description="Text field uses comb-style spacing (bit 25).",
    )
    rich_text: bool = Field(
        default=False,
        description="Text field supports rich text (bit 26).",
    )

    combo: bool = Field(
        default=False,
        description="Choice field is a combo box (bit 18).",
    )
    edit: bool = Field(
        default=False,
        description="Choice field allows editing (bit 19).",
    )
    sort: bool = Field(
        default=False,
        description="Choice field options should be sorted (bit 20).",
    )
    multi_select: bool = Field(
        default=False,
        description="Choice field allows multiple selections (bit 22).",
    )
    commit_on_sel_change: bool = Field(
        default=False,
        description="Commit choice value immediately on selection change (bit 27).",
    )


class RowGroup(BaseModel):
    """Representation of list of PDF fields in one row."""

    fields: list["PDFField"] = Field(
        default_factory=list,
        description="Ordered list of PDF fields appearing in this row.",
    )
    page_index: int = Field(
        default=0,
        description="Zero-based index of the page where this row appears.",
    )


class PDFField(BaseModel):
    """Representation of a single PDF form field."""

    name: str = Field(
        ...,
        description="Original PDF field name for source traceability and conversion mapping.",
    )
    id: str = Field(
        ...,
        description="Unique identifier of the PDF field.",
    )
    type: PDFFieldType = Field(
        ...,
        description="Intermediate field type used for SurveyJS-oriented conversion.",
    )
    field_flags: FieldFlags | None = Field(
        default=None,
        description="Parsed PDF field flags as human-readable booleans.",
    )

    visual_x: int | None = Field(
        default=None,
        description="Horizontal position of the field on the page.",
    )
    visual_y: int | None = Field(
        default=None,
        description="Vertical position of the field on the page.",
    )
    visual_width: int | None = Field(
        default=None,
        description="Width of the field's visual bounding box.",
    )
    visual_height: int | None = Field(
        default=None,
        description="Height of the field's visual bounding box.",
    )

    default_value: str | bool | list[str] | None = Field(
        default=None,
        description="Default value of the field as defined in the PDF.",
    )
    value: str | bool | list[str] | None = Field(
        default=None,
        description="Current field value; list values are only used for multi-select fields.",
    )
    value_options: list[str] = Field(
        default_factory=list,
        description="List of available options for choice-based fields.",
    )
    format: str | None = Field(
        default=None,
        description="Optional display or parsing format for datefield values.",
    )

    max_length: int | None = Field(
        default=None,
        description="Maximum number of characters allowed (text fields).",
    )
    textarea_rows: int | None = Field(
        default=None,
        description="Number of rows for textarea fields.",
    )
    textarea_cols: int | None = Field(
        default=None,
        description="Number of columns for textarea fields.",
    )
