"""PDF Form Extractor module using pypdf."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    StreamObject,
    TextStringObject,
)


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


class _PypdfWarningFilter(logging.Filter):
    """Filter noisy non-fatal pypdf warnings."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "Annotation sizes differ:" not in record.getMessage()


def _install_pypdf_warning_filter() -> None:
    """Install warning filter once for pypdf logger."""
    for logger_name in ("pypdf", "pypdf.generic._link"):
        logger = logging.getLogger(logger_name)
        if not any(isinstance(f, _PypdfWarningFilter) for f in logger.filters):
            logger.addFilter(_PypdfWarningFilter())


def cluster_y_positions(
    y_positions: list[float], default_threshold: float = 15.0
) -> dict[float, float]:
    """Cluster Y positions into rows using adaptive gap detection.

    This function analyzes the distribution of Y coordinates and groups
    positions that are likely part of the same visual row. It uses
    statistical analysis of gaps between consecutive positions to
    automatically determine an appropriate threshold.

    The algorithm works by:
    1. Sorting all Y positions
    2. Calculating gaps between consecutive positions
    3. Using percentile analysis to find natural row breaks
    4. Clustering positions where gaps are smaller than the adaptive threshold

    This approach adapts to different form layouts - tight forms with small
    row spacing and loose forms with large row spacing are both handled well.

    Args:
        y_positions: List of Y coordinates from form fields.
        default_threshold: Maximum within-row gap (default 15.0).

    Returns:
        Dictionary mapping each original Y position to its cluster center.
    """
    if not y_positions:
        return {}

    if len(y_positions) == 1:
        return {y_positions[0]: y_positions[0]}

    # Sort positions and remove duplicates
    sorted_y = sorted(set(y_positions))

    if len(sorted_y) == 1:
        return {sorted_y[0]: sorted_y[0]}

    # Calculate gaps between consecutive positions
    gaps = [sorted_y[i + 1] - sorted_y[i] for i in range(len(sorted_y) - 1)]
    sorted_gaps = sorted(gaps)

    # Find the within-row threshold using gap analysis
    # Strategy: find the largest gap that is likely "within-row" vs "between-row"
    # We use the 25th percentile of gaps as the base threshold
    # This separates tight clusters (within rows) from large gaps (between rows)
    q1_idx = len(sorted_gaps) // 4  # 25th percentile

    # Within-row variation: use 25th percentile as base
    # This captures the typical "within row" variation
    within_row_threshold = sorted_gaps[q1_idx] if q1_idx < len(sorted_gaps) else default_threshold

    # Adaptive threshold: 75th percentile + small buffer, capped at reasonable max
    # The buffer accounts for slight variations, but we cap it to prevent over-grouping
    threshold = min(within_row_threshold * 1.5, default_threshold)

    # Ensure threshold is reasonable (between 10 and default_threshold)
    threshold = max(10.0, min(threshold, default_threshold))

    # Cluster positions
    clusters: list[list[float]] = []
    current_cluster: list[float] = [sorted_y[0]]

    for i in range(1, len(sorted_y)):
        gap = sorted_y[i] - sorted_y[i - 1]
        if gap <= threshold:
            # Same cluster (row)
            current_cluster.append(sorted_y[i])
        else:
            # New cluster (row)
            clusters.append(current_cluster)
            current_cluster = [sorted_y[i]]

    clusters.append(current_cluster)

    # Map each position to its cluster center (mean of cluster)
    position_to_cluster: dict[float, float] = {}
    for cluster in clusters:
        center = sum(cluster) / len(cluster)
        for pos in cluster:
            position_to_cluster[pos] = center

    return position_to_cluster


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
    """

    page: int
    rect: tuple[float, float, float, float]

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

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with page, rect, x, y, width, height, normalized_y, units.
        """
        return {
            "page": self.page,
            "rect": list(self.rect),
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "normalized_y": self.normalized_y,
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
        source: Path,
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


class PDFFormExtractor:
    """Extracts form information from PDF files using pypdf.

    This class provides methods to extract form data from PDF files.
    It uses pypdf for all operations including form extraction and filling.

    Example:
        >>> extractor = PDFFormExtractor()
        >>> form_data = extractor.extract("form.pdf")
        >>> for field in form_data.fields:
        ...     print(f"{field.name}: {field.value}")
        ...     if field.geometry:
        ...         print(f"  Position: ({field.geometry.x}, {field.geometry.y})")
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        extract_geometry: bool = True,
    ) -> None:
        """Initialize the extractor.

        Args:
            timeout_seconds: Timeout for operations (kept for API compatibility).
            extract_geometry: Whether to extract field geometry information.
        """
        self._timeout_seconds = timeout_seconds
        self._extract_geometry = extract_geometry
        self._last_fill_backend = "pypdf"
        self._last_fill_backend_reason: str | None = None
        _install_pypdf_warning_filter()

    @property
    def last_fill_backend(self) -> str:
        """Return the backend used for the most recent fill operation."""
        return self._last_fill_backend

    @property
    def last_fill_backend_reason(self) -> str | None:
        """Return an optional explanation for the most recent backend choice."""
        return self._last_fill_backend_reason

    @staticmethod
    def _get_field_type(field: dict[str, Any]) -> str:
        """Determine field type from pypdf field data.

        Args:
            field: Field dictionary from pypdf.

        Returns:
            Field type string.
        """
        ft = field.get("/FT")
        if ft is None:
            # Try to get from field type name
            ft = field.get("/Type")

        if ft == "/Tx":
            # Check if it's a date field
            if "/AA" in field or "/DV" in field:
                # Look for date format in additional actions
                return "textfield"
            return "textfield"
        elif ft == "/Btn":
            # Button can be checkbox, radio button, or push button
            # Check for radio button group
            if "/Opt" in field:
                return "radiobuttongroup"
            # Check if it's a checkbox (usually has /V as /Yes or /Off)
            return "checkbox"
        elif ft == "/Ch":
            # Choice field - can be combo box or list box
            ff = field.get("/Ff", 0)
            if isinstance(ff, int) and ff & 0x40000:  # Combo box flag
                return "combobox"
            return "listbox"
        elif ft == "/Sig":
            return "signature"

        return "textfield"  # Default fallback

    @staticmethod
    def _get_field_value(field: dict[str, Any]) -> str | bool:
        """Extract value from pypdf field data.

        Args:
            field: Field dictionary from pypdf.

        Returns:
            Field value (string or boolean for checkboxes).
        """
        value = field.get("/V")

        if value is None:
            return ""

        # Handle checkbox values
        if isinstance(value, str):
            if value.lower() in ("/yes", "yes", "/on", "on", "1"):
                return True
            elif value.lower() in ("/off", "off", "no", "0"):
                return False
            return value

        # Handle NameObject from pypdf
        if hasattr(value, "name"):
            name = value.name
            if name.lower() in ("/yes", "yes", "/on", "on", "1"):
                return True
            elif name.lower() in ("/off", "off", "no", "0"):
                return False
            return str(name)

        return str(value)

    @staticmethod
    def _get_field_options(field: dict[str, Any]) -> list[str]:
        """Extract options for choice/radio fields.

        Args:
            field: Field dictionary from pypdf.

        Returns:
            List of option strings.
        """
        options = field.get("/Opt", [])
        if options:
            result = []
            for opt in options:
                # Options can be text or [export_value, label]
                if isinstance(opt, list) and len(opt) >= 2:
                    result.append(str(opt[1]))
                elif isinstance(opt, list) and len(opt) == 1:
                    result.append(str(opt[0]))
                else:
                    result.append(str(opt))
            return result

        # For radio buttons, check Kids
        kids = field.get("/Kids", [])
        if kids:
            # Extract options from kid widgets
            opt_list = []
            for kid in kids:
                kid_obj = kid.get_object() if hasattr(kid, "get_object") else kid
                if kid_obj and "/AP" in kid_obj:
                    ap = kid_obj["/AP"]
                    if "/N" in ap:
                        # Get the appearance names
                        names = list(ap["/N"].keys())
                        opt_list.extend([str(n) for n in names if str(n).lower() != "/off"])
            return list(dict.fromkeys(opt_list))  # Deduplicate while preserving order

        return []

    def has_form(self, pdf_path: str | Path) -> bool:
        """Check if a PDF contains a form.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            True if the PDF contains a form, False otherwise.
        """
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields()
        return fields is not None and len(fields) > 0

    _DEFAULT_ROW_GAP_THRESHOLD = 15.0  # Default gap threshold for row detection

    def _sort_fields(self, fields: list[PDFField]) -> list[PDFField]:
        """Sort fields by page number and position.

        Sorting order:
        1. Page number (ascending)
        2. Y position (descending - top to bottom in PDF coordinates)
        3. X position (ascending - left to right)

        Fields are grouped into rows using adaptive clustering based on the
        distribution of Y coordinates. This handles forms with varying row
        spacing better than a fixed tolerance.

        Args:
            fields: List of PDFField objects to sort.

        Returns:
            Sorted list of PDFField objects.
        """
        # Collect all Y positions for clustering analysis
        y_positions: list[float] = []
        for field in fields:
            if field.geometry:
                y_positions.append(field.geometry.y)

        # Build Y position clusters for row grouping
        y_clusters = cluster_y_positions(y_positions, self._DEFAULT_ROW_GAP_THRESHOLD)

        def sort_key(field: PDFField) -> tuple[int, float, float]:
            page = field.pages[0] if field.pages else 1
            if field.geometry:
                # Use clustered Y for row grouping, original X for ordering
                y_clustered = y_clusters.get(field.geometry.y, field.geometry.y)
                # Y is descending (higher Y = higher on page)
                # X is ascending (left to right)
                return (page, -y_clustered, field.geometry.x)
            return (page, 0.0, 0.0)

        return sorted(fields, key=sort_key)

    def extract(self, pdf_path: str | Path) -> PDFFormData:
        """Extract form data from a PDF file.

        This method extracts form data from the PDF using pypdf and
        parses it into a structured format. If extract_geometry is True,
        field positions and sizes will also be extracted.

        Fields are sorted by page number and position (top-to-bottom,
        left-to-right) for consistent output.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            PDFFormData containing all form information with PDFField objects.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            PDFFormNotFoundError: If the PDF does not contain a form.
        """
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        reader = PdfReader(str(pdf_path))

        # Check if PDF has a form
        fields = reader.get_fields()
        if not fields:
            raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

        # Extract widget info (pages and geometry) in one pass
        widget_info = self._extract_widgets_info(reader)

        # Parse fields into PDFField objects
        pdf_fields: list[PDFField] = []
        raw_fields_data: dict[str, Any] = {}

        for field_counter, (field_name, field_data) in enumerate(fields.items(), start=1):
            raw_fields_data[field_name] = field_data

            # Get field type
            field_type = self._get_field_type(field_data)

            # Get field value
            value = self._get_field_value(field_data)

            # Get info from widget scan
            info = widget_info.get(field_name, ([], None))
            pages = info[0] if info[0] else [1]
            geometry = info[1] if self._extract_geometry else None

            # Get options for choice fields
            options = self._get_field_options(field_data)

            # Create PDFField
            pdf_field = PDFField(
                name=field_name,
                id=str(field_counter),
                type=field_type,
                value=value,
                pages=pages,
                locked=False,  # pypdf doesn't directly expose locked state
                geometry=geometry,
                format=None,  # Date format extraction would require additional parsing
                options=options,
            )
            pdf_fields.append(pdf_field)

        # Sort fields by page and position for consistent output
        pdf_fields = self._sort_fields(pdf_fields)

        # Build raw data structure for compatibility
        raw_data = self._build_raw_data_structure(pdf_fields, str(pdf_path))

        # Get PDF version from header (e.g., "%PDF-1.7" -> "1.7")
        if hasattr(reader, "pdf_header"):
            pdf_version = reader.pdf_header.replace("%PDF-", "")
        else:
            pdf_version = "unknown"

        return PDFFormData(
            source=pdf_path,
            pdf_version=pdf_version,
            has_form=len(pdf_fields) > 0,
            fields=pdf_fields,
            raw_data=raw_data,
        )

    def _get_field_pages(self, reader: PdfReader, field_name: str) -> list[int]:
        """Find which pages contain the field widget (legacy).

        Args:
            reader: PdfReader instance.
            field_name: Name of the field.

        Returns:
            List of 1-based page numbers where field appears.
        """
        widget_info = self._extract_widgets_info(reader)
        return widget_info.get(field_name, ([1], None))[0]

    def _extract_geometry_from_pdf(self, reader: PdfReader) -> dict[str, FieldGeometry]:
        """Extract field geometry from PDF using pypdf (legacy).

        Args:
            reader: PdfReader instance.

        Returns:
            Dictionary mapping field names to FieldGeometry.
        """
        widget_info = self._extract_widgets_info(reader)
        return {name: info[1] for name, info in widget_info.items() if info[1] is not None}

    def _extract_widgets_info(
        self, reader: PdfReader
    ) -> dict[str, tuple[list[int], FieldGeometry | None]]:
        """Scan all pages once to find widget pages and geometry.

        Args:
            reader: PdfReader instance.

        Returns:
            Dictionary mapping field names to (pages_list, geometry_object).
        """
        info: dict[str, tuple[list[int], FieldGeometry | None]] = {}

        for page_num, page in enumerate(reader.pages, start=1):
            if "/Annots" not in page:
                continue

            annots = cast("ArrayObject", page["/Annots"])
            for annot_ref in annots:
                try:
                    annot = (
                        annot_ref.get_object() if hasattr(annot_ref, "get_object") else annot_ref
                    )

                    # Check if it's a widget annotation
                    if annot.get("/Subtype") != "/Widget":
                        continue

                    # Get field name
                    t_value = annot.get("/T")
                    if not t_value:
                        continue

                    field_name = (
                        str(t_value)
                        if isinstance(t_value, str)
                        else str(getattr(t_value, "name", t_value))
                    )

                    # Get rectangle
                    geometry = None
                    rect = annot.get("/Rect")
                    if rect:
                        x0, y0, x1, y1 = [float(coord) for coord in rect]
                        geometry = FieldGeometry(
                            page=page_num,
                            rect=(x0, y0, x1, y1),
                        )

                    # Update info map
                    if field_name not in info:
                        info[field_name] = ([page_num], geometry)
                    else:
                        pages, existing_geom = info[field_name]
                        if page_num not in pages:
                            pages.append(page_num)
                        # Keep the first geometry if multiple exist (current limitation)
                        if existing_geom is None:
                            info[field_name] = (pages, geometry)

                except Exception:  # noqa: S110
                    pass

        return info

    def _build_raw_data_structure(self, fields: list[PDFField], source: str) -> dict[str, Any]:
        """Build raw data structure for export.

        Args:
            fields: List of PDFField objects.
            source: Source PDF path.

        Returns:
            Dictionary with form data organized by field type.
        """
        raw_data: dict[str, Any] = {
            "header": {"source": source, "version": "pypdf"},
            "forms": [
                {
                    "textfield": [],
                    "datefield": [],
                    "checkbox": [],
                    "radiobuttongroup": [],
                    "combobox": [],
                    "listbox": [],
                    "signature": [],
                }
            ],
        }

        for field in fields:
            field_entry: dict[str, Any] = {
                "pages": field.pages,
                "id": field.id,
                "name": field.name,
                "value": field.value,
                "locked": field.locked,
            }

            # Add type-specific attributes
            if field.field_type == "datefield" and field.format:
                field_entry["format"] = field.format

            if field.options and field.field_type in (
                "radiobuttongroup",
                "combobox",
                "listbox",
            ):
                field_entry["options"] = field.options

            # Add to appropriate list
            if field.field_type in raw_data["forms"][0]:
                raw_data["forms"][0][field.field_type].append(field_entry)
            else:
                # Unknown type, add as textfield
                raw_data["forms"][0]["textfield"].append(field_entry)

        return raw_data

    def extract_to_json(self, pdf_path: str | Path, output_path: str | Path) -> None:
        """Extract form data and save it to a JSON file.

        The output JSON will contain the unified PDFField representation
        with geometry information if available.

        Args:
            pdf_path: Path to the PDF file.
            output_path: Path where the JSON output should be saved.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
        """
        pdf_path = Path(pdf_path)
        output_path = Path(output_path)
        self._validate_pdf_path(pdf_path)

        # Use unified extraction which includes geometry
        form_data = self.extract(pdf_path)

        # Write unified format to JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(form_data.to_dict(), f, indent=2)

    def list_fields(self, pdf_path: str | Path) -> list[PDFField]:
        """List all form fields in a PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of PDFField objects.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
        """
        form_data = self.extract(pdf_path)
        return form_data.fields

    def get_field_value(self, pdf_path: str | Path, field_name: str) -> str | bool | None:
        """Get the value of a specific form field.

        Args:
            pdf_path: Path to the PDF file.
            field_name: Name of the field to retrieve.

        Returns:
            The field value, or None if the field is not found.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
        """
        fields = self.list_fields(pdf_path)
        for field in fields:
            if field.name == field_name:
                return field.value
        return None

    def get_field_by_id(self, pdf_path: str | Path, field_id: str) -> PDFField | None:
        """Get a form field by its ID.

        Args:
            pdf_path: Path to the PDF file.
            field_id: ID of the field to retrieve.

        Returns:
            The PDFField object, or None if the field is not found.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
        """
        fields = self.list_fields(pdf_path)
        for field in fields:
            if field.id == field_id:
                return field
        return None

    def get_field_by_name(self, pdf_path: str | Path, field_name: str) -> PDFField | None:
        """Get a form field by its name.

        Args:
            pdf_path: Path to the PDF file.
            field_name: Name of the field to retrieve.

        Returns:
            The PDFField object, or None if the field is not found.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
        """
        fields = self.list_fields(pdf_path)
        for field in fields:
            if field.name == field_name:
                return field
        return None

    def validate_form_data(
        self,
        pdf_path: str | Path,
        form_data: dict[str, Any],
        *,
        strict: bool = False,
        allow_extra_fields: bool = False,
    ) -> list[str]:
        """Validate form data against PDF form fields.

        This method validates that the provided form data (simple key:value format)
        matches the structure and field types of the PDF form.

        Args:
            pdf_path: Path to the PDF file.
            form_data: The form data to validate (simple format: {"Field Name": value}).
            strict: If True, also checks that all form fields are provided.
            allow_extra_fields: If True, allows fields not present in the form.

        Returns:
            List of validation error messages (empty if valid).

        Raises:
            FileNotFoundError: If the PDF file does not exist.
        """
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        errors: list[str] = []

        # Get the form fields from the PDF
        try:
            form_data_obj = self.extract(pdf_path)
        except PDFFormNotFoundError:
            return ["PDF does not contain a form"]

        # Build lookup by name
        fields_by_name = {f.name: f for f in form_data_obj.fields}

        # Validate each input field
        if not allow_extra_fields:
            for field_name, value in form_data.items():
                if field_name not in fields_by_name:
                    errors.append(f"Field not found in form: '{field_name}'")
                    continue

                field = fields_by_name[field_name]

                # Validate value type matches field type
                if field.field_type == "checkbox" and not isinstance(value, bool):
                    errors.append(
                        f"Field '{field_name}': checkbox value must be boolean, "
                        f"got {type(value).__name__}"
                    )

        # In strict mode, check all form fields are provided
        if strict:
            provided_names = set(form_data.keys())
            for field in form_data_obj.fields:
                if field.name not in provided_names:
                    errors.append(f"Required field not provided: '{field.name}'")

        return errors

    @staticmethod
    def _should_fallback_from_pdfcpu(error_message: str) -> bool:
        """Return True for known pdfcpu form-compatibility failures."""
        normalized = error_message.lower()
        return "required entry=da missing" in normalized or "unexpected panic attack" in normalized

    def fill_form(
        self,
        pdf_path: str | Path,
        form_data: dict[str, Any],
        output_path: str | Path | None = None,
        *,
        validate: bool = True,
    ) -> Path:
        """Fill a PDF form with data.

        This method accepts form data in simple key:value format where keys are
        field names and values are the values to fill.

        Args:
            pdf_path: Path to the PDF file containing the form.
            form_data: The form data to fill (format: {"Field Name": value}).
            output_path: Optional output path. If not provided, the input PDF
                        is modified in place.
            validate: If True, validates form data before filling.

        Returns:
            Path to the filled PDF (output_path or pdf_path if no output specified).

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            FormValidationError: If validation fails and validate=True.
            PDFFormNotFoundError: If the PDF does not contain a form.

        Example:
            >>> form_data = {"Candidate Name": "John Smith", "Full time": True}
            >>> extractor.fill_form("form.pdf", form_data, "filled.pdf")
        """
        self._last_fill_backend = "pypdf"
        self._last_fill_backend_reason = None
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        # Check if PDF has a form
        if not self.has_form(pdf_path):
            raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

        # Validate form data if requested
        if validate:
            errors = self.validate_form_data(pdf_path, form_data)
            if errors:
                raise FormValidationError("Form data validation failed", errors)

        # Read the PDF
        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields() or {}
        writer = PdfWriter()

        # Copy all pages and form fields
        writer.append(reader)

        # Fill form fields - collect all values first
        field_values: dict[str, str] = {}
        radio_field_values: dict[str, str] = {}
        listbox_field_values: dict[str, str] = {}
        for field_name, value in form_data.items():
            # pypdf expects string values
            # For checkboxes, use /Yes or /Off
            str_value = ("/Yes" if value else "/Off") if isinstance(value, bool) else str(value)
            field_values[field_name] = str_value
            field_type = self._get_field_type(fields.get(field_name, {}))
            if field_type == "radiobuttongroup":
                radio_field_values[field_name] = str_value
            elif field_type == "listbox":
                listbox_field_values[field_name] = str_value

        # Update all fields at once on all pages where they appear
        if field_values:
            try:
                # We need to call update_page_form_field_values for each page
                # to ensure all widgets are updated. pypdf 5+ correctly handles
                # this by only updating widgets present on the passed page.
                for page in writer.pages:
                    writer.update_page_form_field_values(
                        page,
                        field_values,
                    )
            except AttributeError as exc:
                # Work around pypdf appearance-generation crashes on some PDFs
                # (e.g. "'int' object has no attribute 'encode'").
                if "'int' object has no attribute 'encode'" not in str(exc):
                    raise
                self._fill_form_fields_without_appearance(writer, field_values)
            if radio_field_values:
                self._sync_radio_button_states(writer, radio_field_values)
            if listbox_field_values:
                self._sync_listbox_selection_indexes(writer, listbox_field_values)

        # Write output
        output_file = Path(output_path) if output_path else pdf_path
        with open(output_file, "wb") as f:
            writer.write(f)

        return output_file

    def _fill_form_fields_without_appearance(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Fallback form fill that skips appearance-stream generation."""
        writer.set_need_appearances_writer(True)
        radio_field_values: dict[str, str] = {}
        for page in writer.pages:
            annotations = page.get("/Annots", [])
            if not annotations:
                continue

            for annotation_ref in annotations:
                annotation = annotation_ref.get_object()
                if annotation.get("/Subtype", "") != "/Widget":
                    continue

                if "/FT" in annotation and "/T" in annotation:
                    parent_annotation = annotation
                else:
                    parent_ref = annotation.get("/Parent")
                    parent_annotation = parent_ref.get_object() if parent_ref else annotation

                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")

                matched_field_name = None
                for field_name in field_values:
                    if field_name in (qualified_name, annotation_name, parent_name):
                        matched_field_name = field_name
                        break
                if matched_field_name is None:
                    continue

                value = field_values[matched_field_name]
                field_type = parent_annotation.get("/FT", annotation.get("/FT"))
                if field_type == "/Btn":
                    if self._get_field_type(parent_annotation) == "radiobuttongroup":
                        text_value = TextStringObject(value)
                        parent_annotation[NameObject("/V")] = text_value
                        annotation[NameObject("/V")] = text_value
                        radio_field_values[matched_field_name] = value
                    else:
                        button_value = NameObject(value if value.startswith("/") else f"/{value}")
                        parent_annotation[NameObject("/V")] = button_value
                        annotation[NameObject("/V")] = button_value
                        annotation[NameObject("/AS")] = button_value
                else:
                    text_value = TextStringObject(value)
                    parent_annotation[NameObject("/V")] = text_value
                    annotation[NameObject("/V")] = text_value

        if radio_field_values:
            self._sync_radio_button_states(writer, radio_field_values)

        listbox_field_values = {
            field_name: value
            for field_name, value in field_values.items()
            if self._get_field_type(self.get_field_by_name_from_writer(writer, field_name) or {})
            == "listbox"
        }
        if listbox_field_values:
            self._sync_listbox_selection_indexes(writer, listbox_field_values)

    def get_field_by_name_from_writer(
        self,
        writer: PdfWriter,
        field_name: str,
    ) -> dict[str, Any] | None:
        """Find a field annotation by name in writer pages."""
        for page in writer.pages:
            annotations = page.get("/Annots", [])
            for annotation_ref in annotations:
                annotation, parent_annotation = self._get_widget_annotation(annotation_ref)
                if annotation.get("/Subtype", "") != "/Widget":
                    continue
                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")
                if field_name in (qualified_name, annotation_name, parent_name):
                    return parent_annotation
        return None

    @staticmethod
    def _get_widget_annotation(
        annotation_ref: Any,
    ) -> tuple[DictionaryObject, DictionaryObject]:
        """Resolve widget and parent annotations."""
        annotation = cast(
            "DictionaryObject",
            (
                annotation_ref.get_object()
                if hasattr(annotation_ref, "get_object")
                else annotation_ref
            ),
        )
        parent_ref = annotation.get("/Parent")
        parent_annotation = cast(
            "DictionaryObject",
            parent_ref.get_object() if parent_ref else annotation,
        )
        return annotation, parent_annotation

    @staticmethod
    def _get_widget_on_state(annotation: dict[str, Any]) -> str | None:
        """Return the non-Off appearance state for a widget, if any."""
        ap = annotation.get("/AP")
        if not ap or "/N" not in ap:
            return None

        for state in ap["/N"]:
            state_name = str(state)
            if state_name.lower() != "/off":
                return state_name
        return None

    @classmethod
    def _resolve_radio_field_state(
        cls,
        parent_annotation: dict[str, Any],
        value: str,
    ) -> str:
        """Resolve the selected on-state name for a radio group."""
        normalized_value = value if value.startswith("/") else f"/{value}"
        kids = parent_annotation.get("/Kids", [])

        for kid_ref in kids:
            kid_annotation = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
            kid_state = cls._get_widget_on_state(kid_annotation)
            if kid_state == normalized_value:
                return normalized_value

        options = cls._get_field_options(parent_annotation)
        if options:
            option_value = value[1:] if value.startswith("/") else value
            for index, option in enumerate(options):
                if option != option_value or index >= len(kids):
                    continue
                kid_annotation = (
                    kids[index].get_object() if hasattr(kids[index], "get_object") else kids[index]
                )
                kid_state = cls._get_widget_on_state(kid_annotation)
                if kid_state is not None:
                    return kid_state

        for kid_ref in kids:
            kid_annotation = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
            kid_state = cls._get_widget_on_state(kid_annotation)
            if kid_state and kid_state.lstrip("/") == value.lstrip("/"):
                return kid_state

        return "/Off"

    def _sync_radio_button_states(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Update radio widget appearances to match the selected option."""
        for page in writer.pages:
            annotations = page.get("/Annots", [])
            if not annotations:
                continue

            for annotation_ref in annotations:
                annotation, parent_annotation = self._get_widget_annotation(annotation_ref)
                if annotation.get("/Subtype", "") != "/Widget":
                    continue
                if parent_annotation.get("/FT", annotation.get("/FT")) != "/Btn":
                    continue
                if self._get_field_type(parent_annotation) != "radiobuttongroup":
                    continue

                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")

                matched_field_name = None
                for field_name in field_values:
                    if field_name in (qualified_name, annotation_name, parent_name):
                        matched_field_name = field_name
                        break
                if matched_field_name is None:
                    continue

                selected_state = self._resolve_radio_field_state(
                    parent_annotation,
                    field_values[matched_field_name],
                )
                widget_state = self._get_widget_on_state(annotation)
                state = selected_state if widget_state == selected_state else "/Off"
                parent_annotation[NameObject("/V")] = NameObject(selected_state)
                annotation[NameObject("/AS")] = NameObject(state)
                annotation[NameObject("/V")] = NameObject(state)

    @staticmethod
    def _resolve_listbox_index(parent_annotation: dict[str, Any], value: str) -> int | None:
        """Resolve the selected index for a listbox value."""
        options = PDFFormExtractor._get_field_options(parent_annotation)
        normalized_value = value[1:] if value.startswith("/") else value
        for index, option in enumerate(options):
            if option == normalized_value:
                return index
        return None

    def _sync_listbox_selection_indexes(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Update listbox values and selection indexes for viewer highlighting."""
        for page in writer.pages:
            annotations = page.get("/Annots", [])
            if not annotations:
                continue

            for annotation_ref in annotations:
                annotation, parent_annotation = self._get_widget_annotation(annotation_ref)
                if annotation.get("/Subtype", "") != "/Widget":
                    continue
                if parent_annotation.get("/FT", annotation.get("/FT")) != "/Ch":
                    continue
                if self._get_field_type(parent_annotation) != "listbox":
                    continue

                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")

                matched_field_name = None
                for field_name in field_values:
                    if field_name in (qualified_name, annotation_name, parent_name):
                        matched_field_name = field_name
                        break
                if matched_field_name is None:
                    continue

                value = field_values[matched_field_name]
                selected_index = self._resolve_listbox_index(parent_annotation, value)
                text_value = TextStringObject(value)
                parent_annotation[NameObject("/V")] = text_value
                annotation[NameObject("/V")] = text_value
                if selected_index is not None:
                    indexes = ArrayObject([NumberObject(selected_index)])
                    parent_annotation[NameObject("/I")] = indexes
                    annotation[NameObject("/I")] = ArrayObject([NumberObject(selected_index)])
                    parent_annotation[NameObject("/TI")] = NumberObject(selected_index)
                    annotation[NameObject("/TI")] = NumberObject(selected_index)
                appearance_ref = self._build_listbox_appearance_stream(
                    writer,
                    annotation,
                    parent_annotation,
                    selected_index,
                )
                if appearance_ref is not None:
                    if "/AP" not in annotation:
                        annotation[NameObject("/AP")] = DictionaryObject()
                    appearance_dict = cast("DictionaryObject", annotation["/AP"])
                    appearance_dict[NameObject("/N")] = appearance_ref

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        """Escape text for use in a PDF string literal."""
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _build_listbox_appearance_stream(
        self,
        writer: PdfWriter,
        annotation: dict[str, Any],
        parent_annotation: dict[str, Any],
        selected_index: int | None,
    ) -> Any | None:
        """Build a listbox appearance stream with highlighted selection."""
        options = self._get_field_options(parent_annotation)
        if not options:
            return None

        ap = annotation.get("/AP")
        normal_ap = ap.get("/N").get_object() if ap and "/N" in ap else None
        resources = (
            cast("DictionaryObject", normal_ap.get("/Resources"))
            if normal_ap is not None and "/Resources" in normal_ap
            else DictionaryObject()
        )

        bbox = (
            normal_ap.get("/BBox")
            if normal_ap is not None and "/BBox" in normal_ap
            else ArrayObject(
                [NumberObject(0), NumberObject(0), NumberObject(150), NumberObject(60)]
            )
        )
        width = float(bbox[2]) - float(bbox[0])
        height = float(bbox[3]) - float(bbox[1])
        line_height = height / max(len(options), 1)
        font_size = max(8.0, min(12.0, line_height * 0.75))

        font_name = "/F0"
        if "/Font" in resources and resources["/Font"]:
            fonts = cast("DictionaryObject", resources["/Font"])
            font_name = str(next(iter(fonts.keys())))

        lines: list[str] = [
            "q",
            "/Tx BMC",
            "q",
            f"1 1 {max(width - 2, 1):.3f} {max(height - 2, 1):.3f} re",
            "W",
            "n",
        ]
        if selected_index is not None:
            highlight_y = height - (selected_index + 1) * line_height
            lines.extend(
                [
                    "0.600006 0.756866 0.854904 rg",
                    f"1 {highlight_y:.3f} {max(width - 2, 1):.3f} {line_height:.3f} re",
                    "f",
                ]
            )

        lines.extend(
            [
                "BT",
                f"{font_name} {font_size:.3f} Tf",
            ]
        )
        for index, option in enumerate(options):
            lines.append("1 g" if index == selected_index else "0 g")
            text_y = height - ((index + 1) * line_height) + ((line_height - font_size) / 2)
            escaped = self._escape_pdf_text(str(option))
            lines.append(f"1 0 0 1 2 {text_y:.3f} Tm")
            lines.append(f"({escaped}) Tj")
        lines.extend(["ET", "Q", "EMC", "Q"])

        stream = StreamObject()
        stream[NameObject("/Type")] = NameObject("/XObject")
        stream[NameObject("/Subtype")] = NameObject("/Form")
        stream[NameObject("/BBox")] = bbox
        stream[NameObject("/Resources")] = resources
        stream.set_data("\n".join(lines).encode("utf-8"))
        return writer._add_object(stream)

    def fill_form_from_json(
        self,
        pdf_path: str | Path,
        json_path: str | Path,
        output_path: str | Path | None = None,
        *,
        validate: bool = True,
    ) -> Path:
        """Fill a PDF form with data from a JSON file.

        The JSON file should contain simple key:value pairs where keys are
        field names and values are the values to fill.

        Args:
            pdf_path: Path to the PDF file containing the form.
            json_path: Path to the JSON file with form data.
            output_path: Optional output path. If not provided, the input PDF
                        is modified in place.
            validate: If True, validates form data before filling.

        Returns:
            Path to the filled PDF.

        Raises:
            FileNotFoundError: If any file does not exist.
            FormValidationError: If validation fails and validate=True.
        """
        pdf_path = Path(pdf_path)
        json_path = Path(json_path)

        self._validate_pdf_path(pdf_path)
        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        if not json_path.is_file():
            raise FileNotFoundError(f"Path is not a file: {json_path}")

        # Read and parse JSON
        with open(json_path, encoding="utf-8") as f:
            form_data: dict[str, Any] = json.load(f)

        return self.fill_form(pdf_path, form_data, output_path, validate=validate)

    def _run_pdfcpu_command(self, cmd: list[str]) -> None:
        """Run a pdfcpu command and normalize execution failures."""
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"pdfcpu failed with exit code {e.returncode}"
            if e.stderr:
                error_msg += f": {e.stderr}"
            raise PDFFormError(error_msg) from e
        except subprocess.TimeoutExpired as e:
            raise PDFFormError(f"pdfcpu timed out after {self._timeout_seconds} seconds") from e
        except FileNotFoundError as e:
            raise PDFFormError(f"pdfcpu binary not found: {cmd[0]}") from e

    def _export_pdfcpu_form_data(self, pdf_path: Path, pdfcpu_binary: str) -> dict[str, Any]:
        """Export a PDF form using pdfcpu so its full field metadata is preserved."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as temp_json:
            temp_json_path = Path(temp_json.name)

        try:
            self._run_pdfcpu_command(
                [pdfcpu_binary, "form", "export", str(pdf_path), str(temp_json_path)]
            )

            with open(temp_json_path, encoding="utf-8") as f:
                return cast("dict[str, Any]", json.load(f))
        finally:
            if temp_json_path.exists():
                temp_json_path.unlink()

    @staticmethod
    def _build_pdfcpu_field_index(
        pdfcpu_data: dict[str, Any],
    ) -> tuple[dict[str, tuple[str, dict[str, Any]]], dict[str, tuple[str, dict[str, Any]]]]:
        """Index exported pdfcpu fields by exact and terminal field name."""
        exact_matches: dict[str, tuple[str, dict[str, Any]]] = {}
        suffix_candidates: dict[str, list[tuple[str, dict[str, Any]]]] = {}

        for form in pdfcpu_data.get("forms", []):
            if not isinstance(form, dict):
                continue

            for field_type, entries in form.items():
                if not isinstance(entries, list):
                    continue

                for entry in entries:
                    if not isinstance(entry, dict):
                        continue

                    field_id = entry.get("id")
                    if field_id is not None:
                        exact_matches[str(field_id)] = (field_type, entry)

                    field_name = entry.get("name")
                    if field_name is None:
                        continue

                    field_name_str = str(field_name)
                    exact_matches[field_name_str] = (field_type, entry)
                    suffix_candidates.setdefault(field_name_str.rsplit(".", 1)[-1], []).append(
                        (field_type, entry)
                    )

        suffix_matches = {
            suffix: matches[0] for suffix, matches in suffix_candidates.items() if len(matches) == 1
        }

        return exact_matches, suffix_matches

    def _merge_pdfcpu_form_data(
        self,
        pdfcpu_data: dict[str, Any],
        form_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge simple key:value form data into exported pdfcpu JSON."""
        exact_matches, suffix_matches = self._build_pdfcpu_field_index(pdfcpu_data)

        for field_name, value in form_data.items():
            lookup_key = str(field_name)
            field_match = exact_matches.get(lookup_key) or suffix_matches.get(lookup_key)
            if field_match is None:
                continue

            field_type, field_entry = field_match

            if field_type == "checkbox":
                field_entry["value"] = bool(value)
                continue

            if field_type == "listbox":
                if isinstance(value, list):
                    field_entry.pop("value", None)
                    field_entry["values"] = [str(item) for item in value]
                else:
                    field_entry.pop("values", None)
                    field_entry["value"] = str(value)
                continue

            field_entry["value"] = str(value)

        return pdfcpu_data

    def fill_form_with_pdfcpu(
        self,
        pdf_path: str | Path,
        form_data: dict[str, Any],
        output_path: str | Path | None = None,
        *,
        validate: bool = True,
        pdfcpu_path: str = "pdfcpu",
    ) -> Path:
        """Fill a PDF form with data using pdfcpu.

        This method uses the external pdfcpu binary to fill PDF forms.
        pdfcpu must be installed and available in the system PATH or
        specified via the pdfcpu_path parameter.

        Args:
            pdf_path: Path to the PDF file containing the form.
            form_data: The form data to fill (format: {"Field Name": value}).
            output_path: Optional output path. If not provided, the input PDF
                        is modified in place.
            validate: If True, validates form data before filling using pypdf.
            pdfcpu_path: Path to the pdfcpu binary (default: "pdfcpu").

        Returns:
            Path to the filled PDF (output_path or pdf_path if no output specified).

        Raises:
            FileNotFoundError: If the PDF file or pdfcpu binary does not exist.
            FormValidationError: If validation fails and validate=True.
            PDFFormNotFoundError: If the PDF does not contain a form.
            PDFFormError: If pdfcpu execution fails.

        Example:
            >>> form_data = {"Candidate Name": "John Smith", "Full time": True}
            >>> extractor.fill_form_with_pdfcpu("form.pdf", form_data, "filled.pdf")
        """
        self._last_fill_backend = "pdfcpu"
        self._last_fill_backend_reason = None
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        # Check if pdfcpu is available
        pdfcpu_binary = shutil.which(pdfcpu_path)
        if pdfcpu_binary is None:
            raise PDFFormError(
                f"pdfcpu binary not found: {pdfcpu_path}. "
                "Please install pdfcpu: https://pdfcpu.io/install"
            )

        # Check if PDF has a form
        if not self.has_form(pdf_path):
            raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

        # Validate form data if requested
        if validate:
            errors = self.validate_form_data(pdf_path, form_data)
            if errors:
                raise FormValidationError("Form data validation failed", errors)

        # Prepare output path
        output_file = Path(output_path) if output_path else pdf_path

        try:
            # Export the form via pdfcpu first and only update its values. Some PDFs
            # require metadata in the exported JSON that pypdf does not expose.
            pdfcpu_json_data = self._merge_pdfcpu_form_data(
                self._export_pdfcpu_form_data(pdf_path, pdfcpu_binary),
                form_data,
            )
        except PDFFormError as exc:
            if not self._should_fallback_from_pdfcpu(str(exc)):
                raise

            result = self.fill_form(pdf_path, form_data, output_file, validate=False)
            self._last_fill_backend = "pypdf-fallback"
            self._last_fill_backend_reason = (
                "pdfcpu could not process the source form metadata; used pypdf instead"
            )
            return result

        # Create a temporary JSON file for pdfcpu
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as temp_json:
            json.dump(pdfcpu_json_data, temp_json, indent=2)
            temp_json_path = Path(temp_json.name)

        try:
            # Build pdfcpu command
            # pdfcpu form fill <inFile> <formDataFile> <outFile>
            cmd = [
                pdfcpu_binary,
                "form",
                "fill",
                str(pdf_path),
                str(temp_json_path),
                str(output_file),
            ]

            try:
                self._run_pdfcpu_command(cmd)
            except PDFFormError as exc:
                if not self._should_fallback_from_pdfcpu(str(exc)):
                    raise

                result = self.fill_form(pdf_path, form_data, output_file, validate=False)
                self._last_fill_backend = "pypdf-fallback"
                self._last_fill_backend_reason = (
                    "pdfcpu could not process the source form metadata; used pypdf instead"
                )
                return result

            # Verify output file was created
            if not output_file.exists():
                raise PDFFormError(f"pdfcpu did not create output file: {output_file}")

            return output_file

        finally:
            # Clean up temporary JSON file
            if temp_json_path.exists():
                temp_json_path.unlink()

    def _validate_pdf_path(self, pdf_path: Path) -> None:
        """Validate that the PDF path exists and is a file.

        Args:
            pdf_path: Path to validate.

        Raises:
            FileNotFoundError: If the path does not exist or is not a file.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Path is not a file: {pdf_path}")


def is_pdfcpu_available(pdfcpu_path: str = "pdfcpu") -> bool:
    """Check if pdfcpu binary is available.

    Args:
        pdfcpu_path: Path to the pdfcpu binary (default: "pdfcpu").

    Returns:
        True if pdfcpu is available in the system PATH, False otherwise.
    """
    return shutil.which(pdfcpu_path) is not None


def get_available_geometry_backends() -> list[str]:
    """Return list of available geometry backends.

    Returns:
        List of backend names that can be used.
        For pypdf version, always returns ["pypdf"].
    """
    return ["pypdf"]


def has_geometry_support() -> bool:
    """Check if any geometry extraction backend is available.

    Returns:
        True (pypdf always supports geometry extraction).
    """
    return True


# Backwards compatibility aliases (deprecated, will be removed in a future version)
# These aliases exist for code that was written for earlier versions using pdfcpu
PDFCPUError = PDFFormError
PDFCPUNotFoundError = PDFFormError
PDFCPUExecutionError = PDFFormError
