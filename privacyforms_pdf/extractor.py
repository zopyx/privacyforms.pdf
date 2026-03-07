"""PDF Form Extractor module using pypdf."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader, PdfWriter

if TYPE_CHECKING:
    from pypdf.generic import ArrayObject


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
    """

    page: int
    rect: tuple[float, float, float, float]

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

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary with page, rect, x, y, width, height, units.
        """
        return {
            "page": self.page,
            "rect": list(self.rect),
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
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

    def extract(self, pdf_path: str | Path) -> PDFFormData:
        """Extract form data from a PDF file.

        This method extracts form data from the PDF using pypdf and
        parses it into a structured format. If extract_geometry is True,
        field positions and sizes will also be extracted.

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
        writer = PdfWriter()

        # Copy all pages and form fields
        writer.append(reader)

        # Fill form fields - collect all values first
        field_values = {}
        for field_name, value in form_data.items():
            # pypdf expects string values
            # For checkboxes, use /Yes or /Off
            str_value = ("/Yes" if value else "/Off") if isinstance(value, bool) else str(value)
            field_values[field_name] = str_value

        # Update all fields at once on all pages where they appear
        if field_values:
            # We need to call update_page_form_field_values for each page
            # to ensure all widgets are updated. pypdf 5+ correctly handles
            # this by only updating widgets present on the passed page.
            for page in writer.pages:
                writer.update_page_form_field_values(
                    page,
                    field_values,
                )

        # Write output
        output_file = Path(output_path) if output_path else pdf_path
        with open(output_file, "wb") as f:
            writer.write(f)

        return output_file

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
