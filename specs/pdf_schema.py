from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

    fields: list[PDFField] = Field(
        default_factory=list,
        description="Ordered list of PDF fields appearing in this row.",
    )
    page_index: int = Field(
        default=0,
        description="Zero-based index of the page where this row appears.",
    )


class ChoiceOption(BaseModel):
    """Structured option for choice-based fields."""

    model_config = ConfigDict(extra="forbid")

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
        return normalized

    @field_validator("text", "source_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Normalize blank optional strings to None."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class FieldLayout(BaseModel):
    """Compact layout hints for conversion and visual grouping."""

    model_config = ConfigDict(extra="forbid")

    page: int | None = Field(
        default=None,
        description="Zero-based page index where the field appears.",
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
        return value


class PDFField(BaseModel):
    """Representation of a single PDF form field."""

    model_config = ConfigDict(extra="forbid")

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

    @field_validator("name", "id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """Require non-empty field identifiers."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("field identifiers must not be empty")
        return normalized

    @field_validator("title", "format")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Normalize blank optional strings to None."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("max_length", "textarea_rows", "textarea_cols")
    @classmethod
    def validate_positive_integers(cls, value: int | None) -> int | None:
        """Require positive UI hint values when present."""
        if value is not None and value <= 0:
            raise ValueError("numeric field constraints must be positive")
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

        if self.type == "checkbox" and self.value is not None and not isinstance(self.value, bool):
            raise ValueError("checkbox value must be bool or None")

        if (
            self.type in {"textfield", "textarea", "datefield", "signature"}
            and self.value is not None
            and not isinstance(self.value, str)
        ):
            raise ValueError(f"{self.type} value must be str or None")

        if (
            self.type in {"radiobuttongroup", "combobox"}
            and self.value is not None
            and not isinstance(self.value, str)
        ):
            raise ValueError(f"{self.type} value must be str or None")

        if self.type == "listbox" and isinstance(self.value, list):
            multi_select = self.field_flags.multi_select if self.field_flags is not None else False
            if not multi_select:
                raise ValueError("list-valued listbox value requires field_flags.multi_select")

        if self.type != "listbox" and isinstance(self.value, list):
            raise ValueError("list values are only valid for listbox")

        return self


class PDFRepresentation(BaseModel):
    """Top-level document model for the PDF-to-SurveyJS intermediate format."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    spec_version: str = Field(
        default="1.0",
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

    @field_validator("spec_version")
    @classmethod
    def validate_spec_version(cls, value: str) -> str:
        """Require a non-empty spec version string."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("spec_version must not be empty")
        return normalized

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str | None) -> str | None:
        """Normalize blank source strings to None."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_document(self) -> PDFRepresentation:
        """Enforce document-level constraints."""
        field_ids = [field.id for field in self.fields]
        duplicates = sorted({field_id for field_id in field_ids if field_ids.count(field_id) > 1})
        if duplicates:
            raise ValueError(f"field ids must be unique: {', '.join(duplicates)}")

        valid_ids = {field.id for field in self.fields}
        row_ids = {field.id for row in self.rows for field in row.fields}
        unknown_row_ids = sorted(row_ids - valid_ids)
        if unknown_row_ids:
            missing_ids = ", ".join(unknown_row_ids)
            raise ValueError(
                f"rows reference fields that are not present in fields: {missing_ids}"
            )

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
