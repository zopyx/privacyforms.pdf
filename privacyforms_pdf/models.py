"""Data models and exceptions for privacyforms-pdf."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PDFFormError(Exception):
    """Base exception for PDF form related errors."""

    pass


class PDFFormNotFoundError(PDFFormError):
    """Raised when the PDF does not contain any forms."""

    pass


class FieldNotFoundError(PDFFormError):
    """Raised when a field is not found in the form."""

    pass


class FormValidationError(PDFFormError):
    """Raised when form data validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        """Initialize the error with validation details.

        Args:
            message: Error message.
            errors: List of specific validation errors.
        """
        super().__init__(message)
        self.message = message
        self.errors = errors or []

    def __str__(self) -> str:  # noqa: D105
        if self.errors:
            return f"{self.message}\n- " + "\n- ".join(self.errors)
        return self.message


class FieldGeometry(BaseModel):
    """Geometry information for a PDF form field.

    Attributes:
        page: 1-based page number where field appears.
        rect: Bounding box as (x1, y1, x2, y2) in PDF points (1/72 inch).
        x: Left coordinate.
        y: Bottom coordinate (PDF coordinate system).
        width: Field width in points.
        height: Field height in points.
        units: Unit of measurement (always "pt" for points).
        normalized_y: Y position quantized to 15-point buckets for row grouping.
        row_y: Y position of the row cluster (adaptive clustering for row grouping).
    """

    page: int
    rect: tuple[float, float, float, float]
    # Store computed row_y after clustering analysis
    _row_y: float | None = None

    # Tolerance for position normalization (15 PDF points)
    _POSITION_TOLERANCE: float = 15.0

    @property
    def x(self) -> float:
        """Left coordinate."""
        return self.rect[0]

    @property
    def y(self) -> float:
        """Bottom coordinate (PDF coordinate system)."""
        return self.rect[1]

    @property
    def width(self) -> float:
        """Field width in points."""
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> float:
        """Field height in points."""
        return self.rect[3] - self.rect[1]

    @property
    def normalized_y(self) -> float:
        """Y position quantized to tolerance buckets for row grouping.

        Fields with normalized_y values within +/- tolerance are considered
        to be on the same visual row for sorting and display purposes.
        """
        tolerance = self._POSITION_TOLERANCE
        return round(self.y / tolerance) * tolerance

    @property
    def row_y(self) -> float:
        """Y position of the row cluster center.

        This is computed using adaptive clustering analysis of all field
        positions in the PDF. Fields with the same row_y are on the same
        visual row.

        Returns:
            The cluster center Y coordinate, or the original Y if not clustered.
        """
        if self._row_y is not None:
            return self._row_y
        return self.y

    def set_row_y(self, value: float) -> None:
        """Set the computed row cluster Y position.

        This is called after clustering analysis is performed on all fields.

        Args:
            value: The cluster center Y coordinate.
        """
        self._row_y = value

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with page, rect, x, y, width, height, normalized_y,
            row_y, and units.
        """
        return {
            "page": self.page,
            "rect": list(self.rect),
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "normalized_y": self.normalized_y,
            "row_y": self.row_y,
            "units": "pt",
        }


class PDFField(BaseModel):
    """Unified PDF form field model with geometry and all field properties.

    Attributes:
        name: The name of the field.
        id: The unique identifier of the field.
        field_type: The type of the form field (e.g., 'textfield', 'checkbox').
        value: The current value of the field.
        pages: List of pages where this field appears.
        locked: Whether the field is locked.
        geometry: Optional geometry information (position and size).
        format: Date format for datefield types.
        options: Available options for radiobuttongroup, combobox, listbox types.
    """

    name: str
    id: str
    field_type: str = Field(..., alias="type")
    value: str | bool = ""
    pages: list[int] = []
    locked: bool = False
    geometry: FieldGeometry | None = None
    format: str | None = None
    options: list[str] = []

    model_config = ConfigDict(populate_by_name=True)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Serialize field to dictionary, including geometry if present.

        Returns:
            Dictionary representation of the field.
        """
        data = super().model_dump(**kwargs)
        # Ensure geometry is properly serialized if present
        if self.geometry is not None:
            data["geometry"] = self.geometry.model_dump()
        else:
            data["geometry"] = None
        return data


class FormField:
    """Represents a single form field (legacy dataclass, use PDFField instead).

    Attributes:
        field_type: The type of the form field (e.g., 'textfield', 'checkbox').
        pages: List of pages where this field appears.
        id: The unique identifier of the field.
        name: The name of the field.
        value: The current value of the field.
        locked: Whether the field is locked.
    """

    def __init__(
        self,
        field_type: str,
        pages: list[int],
        id: str,  # noqa: A002
        name: str,
        value: str | bool,
        locked: bool,
    ) -> None:
        """Initialize FormField.

        Args:
            field_type: The type of the form field.
            pages: List of pages where this field appears.
            id: The unique identifier of the field.
            name: The name of the field.
            value: The current value of the field.
            locked: Whether the field is locked.
        """
        self.field_type = field_type
        self.pages = pages
        self.id = id
        self.name = name
        self.value = value
        self.locked = locked

    def __repr__(self) -> str:
        """Return string representation."""
        return f"FormField(field_type='{self.field_type}', name='{self.name}', id='{self.id}')"

    def __eq__(self, other: object) -> bool:
        """Check equality with another FormField."""
        if not isinstance(other, FormField):
            return NotImplemented
        return (
            self.field_type == other.field_type
            and self.pages == other.pages
            and self.id == other.id
            and self.name == other.name
            and self.value == other.value
            and self.locked == other.locked
        )


class PDFFormData:
    """Represents extracted PDF form data.

    Attributes:
        source: Path to the source PDF file.
        pdf_version: Version of the PDF.
        has_form: Whether the PDF contains a form.
        fields: List of PDF fields (PDFField objects).
        raw_data: The raw data from pypdf.
    """

    def __init__(
        self,
        source: Any,
        pdf_version: str,
        has_form: bool,
        fields: list[PDFField],
        raw_data: dict[str, Any],
    ) -> None:
        """Initialize PDFFormData.

        Args:
            source: Path to the source PDF file.
            pdf_version: Version of the PDF.
            has_form: Whether the PDF contains a form.
            fields: List of PDFField objects.
            raw_data: The raw data from pypdf.
        """
        self.source = source
        self.pdf_version = pdf_version
        self.has_form = has_form
        self.fields = fields
        self.raw_data = raw_data

    def to_json(self) -> str:
        """Serialize form data to JSON string.

        Returns:
            JSON string representation of the form data.
        """
        data = {
            "source": str(self.source),
            "pdf_version": self.pdf_version,
            "has_form": self.has_form,
            "fields": [field.model_dump() for field in self.fields],
        }
        return json.dumps(data, indent=2)

    def to_dict(self) -> dict[str, Any]:
        """Serialize form data to dictionary.

        Returns:
            Dictionary representation of the form data.
        """
        return {
            "source": str(self.source),
            "pdf_version": self.pdf_version,
            "has_form": self.has_form,
            "fields": [field.model_dump() for field in self.fields],
        }
