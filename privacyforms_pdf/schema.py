from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)

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

    model_config = ConfigDict(extra="forbid", strict=True)

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

    @model_serializer(mode="wrap")
    def compact_serialize(self, handler):
        """Serialize only True flags to keep JSON compact."""
        data = handler(self)
        return {k: v for k, v in data.items() if v is not False}


class RowGroup(BaseModel):
    """Representation of list of PDF fields in one row."""

    model_config = ConfigDict(extra="forbid", strict=True)

    fields: list[PDFField | str] = Field(
        default_factory=list,
        description=(
            "Ordered list of PDF fields appearing in this row (may be IDs during deserialization)."
        ),
    )
    page_index: int = Field(
        default=1,
        description="One-based index of the page where this row appears.",
    )

    @field_validator("page_index")
    @classmethod
    def validate_page_index(cls, value: int) -> int:
        """Require a positive page index."""
        if value < 1:
            raise ValueError("page_index must be at least 1")
        if value > 100_000:
            raise ValueError("page_index must not exceed 100000")
        return value

    @model_serializer(mode="wrap")
    def serialize_compact(self, handler):
        """Serialize fields as IDs for a compact representation."""
        data = handler(self)
        data["page_index"] = self.page_index
        data["fields"] = [
            field.id if isinstance(field, PDFField) else field for field in self.fields
        ]
        return data


class ChoiceOption(BaseModel):
    """Structured option for choice-based fields."""

    model_config = ConfigDict(extra="forbid", strict=True)

    value: str = Field(
        ...,
        description="Stored value used when the option is selected.",
    )
    text: str | None = Field(
        default=None,
        description="Optional user-facing label for the option.",
    )
    source_name: str | None = Field(
        default=None,
        description="Optional raw source identifier from the PDF extraction layer.",
    )

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        """Require non-empty option values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("choice values must not be empty")
        if len(normalized) > 4096:
            raise ValueError("choice value exceeds maximum length of 4096 characters")
        return normalized

    @field_validator("text", "source_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Normalize blank optional strings to None."""
        if value is None:
            return None
        if len(value) > 4096:
            raise ValueError("field exceeds maximum length of 4096 characters")
        normalized = value.strip()
        return normalized or None


class FieldLayout(BaseModel):
    """Compact layout hints for conversion and visual grouping."""

    model_config = ConfigDict(extra="forbid", strict=True)

    page: int | None = Field(
        default=None,
        description="One-based page index where the field appears.",
    )
    x: int | None = Field(
        default=None,
        description="Horizontal position of the field on the page.",
    )
    y: int | None = Field(
        default=None,
        description="Vertical position of the field on the page.",
    )
    width: int | None = Field(
        default=None,
        description="Width of the field's visual bounding box.",
    )
    height: int | None = Field(
        default=None,
        description="Height of the field's visual bounding box.",
    )

    @field_validator("page", "x", "y", "width", "height")
    @classmethod
    def validate_non_negative(cls, value: int | None) -> int | None:
        """Disallow negative layout values."""
        if value is not None and value < 0:
            raise ValueError("layout values must be non-negative")
        if value is not None and value > 1_000_000:
            raise ValueError("layout values must not exceed 1000000")
        return value


FieldTextRole = Literal[
    "label",
    "description",
    "helper",
    "instruction",
    "unknown",
]

FieldTextDirection = Literal[
    "left",
    "right",
    "above",
    "below",
    "inside",
    "unknown",
]


class FieldTextBlock(BaseModel):
    """A text block geometrically or semantically associated with a form field."""

    model_config = ConfigDict(extra="forbid", strict=True)

    text: str = Field(
        ...,
        description="Raw text content found near the field.",
    )
    role: FieldTextRole = Field(
        default="unknown",
        description="Semantic role of the text relative to the field.",
    )
    direction: FieldTextDirection = Field(
        default="unknown",
        description="Relative position of the text block to the field widget.",
    )
    layout: FieldLayout | None = Field(
        default=None,
        description="Bounding box of the text block on the page.",
    )
    distance: float | None = Field(
        default=None,
        description="Distance in PDF units from the nearest field edge to the text block.",
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        """Require non-empty text with a reasonable length cap.

        Image blocks (block_type == 1) are exempt from the non-empty
        requirement since they carry no textual content.
        """
        if info.data.get("block_type") == 1:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be empty")
        if len(normalized) > 100_000:
            raise ValueError("text exceeds maximum length of 100000 characters")
        return normalized

    @field_validator("distance")
    @classmethod
    def validate_distance(cls, value: float | None) -> float | None:
        """Disallow negative distances."""
        if value is not None and value < 0:
            raise ValueError("distance must be non-negative")
        return value


class TextFormat(BaseModel):
    """Formatting metadata for a text span or block."""

    model_config = ConfigDict(extra="forbid", strict=True)

    font: str | None = Field(
        default=None,
        description="Name of the font family (e.g. 'Helvetica-Bold').",
    )
    font_size: float | None = Field(
        default=None,
        description="Font size in points.",
    )
    color: str | None = Field(
        default=None,
        description="Text color as a hex string (e.g. '#000000').",
    )
    flags: int | None = Field(
        default=None,
        description="Raw PDF font flags integer.",
    )
    bold: bool | None = Field(
        default=None,
        description="Whether the text is bold (derived from flags).",
    )
    italic: bool | None = Field(
        default=None,
        description="Whether the text is italic (derived from flags).",
    )

    @field_validator("font_size")
    @classmethod
    def validate_font_size(cls, value: float | None) -> float | None:
        """Disallow negative font sizes."""
        if value is not None and value < 0:
            raise ValueError("font_size must be non-negative")
        return value


class PDFTextBlock(BaseModel):
    """A text block found anywhere on a PDF page."""

    model_config = ConfigDict(extra="forbid", strict=True)

    block_type: int | None = Field(
        default=None,
        description=("Block type classification: 0 = text, 1 = image (convention from PyMuPDF)."),
    )
    text: str = Field(
        ...,
        description="Extracted text content of the block.",
    )
    layout: FieldLayout | None = Field(
        default=None,
        description="Bounding box of the text block on the page.",
    )
    format: TextFormat | None = Field(
        default=None,
        description="Optional formatting metadata for the block.",
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        """Require non-empty text with a reasonable length cap.

        Image blocks (block_type == 1) are exempt from the non-empty
        requirement since they carry no textual content.
        """
        if info.data.get("block_type") == 1:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be empty")
        if len(normalized) > 100_000:
            raise ValueError("text exceeds maximum length of 100000 characters")
        return normalized


class PDFPage(BaseModel):
    """Content and geometry of a single PDF page."""

    model_config = ConfigDict(extra="forbid", strict=True)

    page_index: int = Field(
        ...,
        description="One-based index of the page.",
    )
    width: float | None = Field(
        default=None,
        description="Page width in PDF points.",
    )
    height: float | None = Field(
        default=None,
        description="Page height in PDF points.",
    )
    text_blocks: list[PDFTextBlock] = Field(
        default_factory=list,
        description="Text blocks extracted from this page.",
    )

    @field_validator("page_index")
    @classmethod
    def validate_page_index(cls, value: int) -> int:
        """Require a positive page index."""
        if value < 1:
            raise ValueError("page_index must be at least 1")
        if value > 100_000:
            raise ValueError("page_index must not exceed 100000")
        return value

    @field_validator("width", "height")
    @classmethod
    def validate_non_negative(cls, value: float | None) -> float | None:
        """Disallow negative page dimensions."""
        if value is not None and value < 0:
            raise ValueError("page dimensions must be non-negative")
        return value


class PDFField(BaseModel):
    """Representation of a single PDF form field."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(
        ...,
        description="Original PDF field name for source traceability and conversion mapping.",
    )
    title: str | None = Field(
        default=None,
        description="Optional user-facing title inferred from nearby labels or conversion logic.",
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
    layout: FieldLayout | None = Field(
        default=None,
        description="Compact layout hints used for grouping and ordering during conversion.",
    )

    default_value: str | bool | list[str] | None = Field(
        default=None,
        description="Default value of the field as defined in the PDF.",
    )
    value: str | bool | list[str] | None = Field(
        default=None,
        description="Current field value; list values are only used for multi-select fields.",
    )
    choices: list[ChoiceOption] = Field(
        default_factory=list,
        description="Structured choices for radio, combo, and list-based fields.",
    )
    text_blocks: list[FieldTextBlock] = Field(
        default_factory=list,
        description=(
            "Nearby text blocks associated with this field "
            "(labels, descriptions, helpers, instructions)."
        ),
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

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Require non-empty field name."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("field name must not be empty")
        if len(normalized) > 2048:
            raise ValueError("field name exceeds maximum length of 2048 characters")
        return normalized

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Require non-empty field id."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("field id must not be empty")
        if len(normalized) > 512:
            raise ValueError("field id exceeds maximum length of 512 characters")
        return normalized

    @field_validator("title", "format")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Normalize blank optional strings to None."""
        if value is None:
            return None
        if len(value) > 4096:
            raise ValueError("field exceeds maximum length of 4096 characters")
        normalized = value.strip()
        return normalized or None

    @field_validator("value", "default_value")
    @classmethod
    def validate_value_length(
        cls, value: str | bool | list[str] | None
    ) -> str | bool | list[str] | None:
        """Enforce maximum length on string and list values."""
        if isinstance(value, str) and len(value) > 100_000:
            raise ValueError("field value exceeds maximum length of 100000 characters")
        if isinstance(value, list) and any(len(item) > 100_000 for item in value):
            raise ValueError("list value item exceeds maximum length of 100000 characters")
        return value

    @field_validator("max_length", "textarea_rows", "textarea_cols")
    @classmethod
    def validate_positive_integers(cls, value: int | None) -> int | None:
        """Require positive UI hint values when present."""
        if value is not None and value <= 0:
            raise ValueError("numeric field constraints must be positive")
        if value is not None and value > 1_000_000:
            raise ValueError("numeric field constraints must not exceed 1000000")
        return value

    @model_validator(mode="after")
    def validate_field_semantics(self) -> PDFField:
        """Enforce type-specific constraints for conversion safety."""
        if self.type != "datefield" and self.format is not None:
            raise ValueError("format is only valid for datefield")

        if self.type != "textarea" and (
            self.textarea_rows is not None or self.textarea_cols is not None
        ):
            raise ValueError("textarea_rows and textarea_cols are only valid for textarea")

        if (
            self.type in {"checkbox", "textfield", "textarea", "datefield", "signature"}
            and self.choices
        ):
            raise ValueError(f"choices are not valid for {self.type}")

        self._validate_scalar_value(self.value, label="value")
        self._validate_scalar_value(self.default_value, label="default_value")

        return self

    def _validate_scalar_value(self, value: str | bool | list[str] | None, *, label: str) -> None:
        """Enforce type-specific rules for value-bearing fields."""
        if self.type == "checkbox" and value is not None and not isinstance(value, bool):
            raise ValueError(f"checkbox {label} must be bool or None")

        if (
            self.type in {"textfield", "textarea", "datefield", "signature"}
            and value is not None
            and not isinstance(value, str)
        ):
            raise ValueError(f"{self.type} {label} must be str or None")

        if (
            self.type in {"radiobuttongroup", "combobox"}
            and value is not None
            and not isinstance(value, str)
        ):
            raise ValueError(f"{self.type} {label} must be str or None")

        if self.type == "listbox" and isinstance(value, list):
            multi_select = self.field_flags.multi_select if self.field_flags is not None else False
            if not multi_select:
                raise ValueError(f"list-valued listbox {label} requires field_flags.multi_select")

        if self.type != "listbox" and isinstance(value, list):
            raise ValueError(f"list values are only valid for listbox {label}")


class PDFRepresentation(BaseModel):
    """Top-level document model for the PDF-to-SurveyJS intermediate format."""

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    spec_version: str = Field(
        default="1.2",
        description="Version of the intermediate representation specification.",
    )
    source: str | None = Field(
        default=None,
        description="Optional path, URL, or identifier of the source PDF.",
    )
    fields: list[PDFField] = Field(
        default_factory=list,
        description="Normalized fillable fields extracted from the PDF.",
    )
    rows: list[RowGroup] = Field(
        default_factory=list,
        description="Optional visual row groupings derived from layout analysis.",
    )
    pages: list[PDFPage] = Field(
        default_factory=list,
        description="All text blocks extracted from each page.",
    )

    @field_validator("spec_version")
    @classmethod
    def validate_spec_version(cls, value: str) -> str:
        """Require a non-empty spec version string."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("spec_version must not be empty")
        if len(normalized) > 32:
            raise ValueError("spec_version exceeds maximum length of 32 characters")
        return normalized

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str | None) -> str | None:
        """Normalize blank source strings to None."""
        if value is None:
            return None
        if len(value) > 4096:
            raise ValueError("source exceeds maximum length of 4096 characters")
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_document(self) -> PDFRepresentation:
        """Enforce document-level constraints and resolve row field IDs."""
        field_ids = [field.id for field in self.fields]
        id_counts = Counter(field_ids)
        duplicates = sorted({field_id for field_id, count in id_counts.items() if count > 1})
        if duplicates:
            raise ValueError(f"field ids must be unique: {', '.join(duplicates)}")

        valid_ids = {field.id for field in self.fields}
        field_map = {field.id: field for field in self.fields}

        # Resolve row field IDs to PDFField objects
        for row in self.rows:
            resolved: list[PDFField | str] = []
            for item in row.fields:
                if isinstance(item, PDFField):
                    resolved.append(item)
                elif isinstance(item, str):
                    if item not in field_map:
                        raise ValueError(
                            f"rows reference fields that are not present in fields: {item}"
                        )
                    resolved.append(field_map[item])
                else:
                    raise ValueError(f"rows contain invalid field reference: {item}")
            row.fields = resolved

        row_ids = {
            field.id for row in self.rows for field in row.fields if isinstance(field, PDFField)
        }
        unknown_row_ids = sorted(row_ids - valid_ids)
        if unknown_row_ids:
            missing_ids = ", ".join(unknown_row_ids)
            raise ValueError(f"rows reference fields that are not present in fields: {missing_ids}")

        return self

    def get_field_by_id(self, field_id: str) -> PDFField | None:
        """Return a field by its stable identifier."""
        for field in self.fields:
            if field.id == field_id:
                return field
        return None

    def get_field_by_name(self, name: str) -> PDFField | None:
        """Return a field by its original PDF field name."""
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def to_compact_json(self, *, indent: int = 2) -> str:
        """Serialize to a compact JSON string, omitting None values and defaults."""
        return self.model_dump_json(exclude_none=True, exclude_defaults=True, indent=indent)
