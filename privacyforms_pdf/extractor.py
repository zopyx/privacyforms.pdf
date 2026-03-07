"""PDF Form Extractor module using pdfcpu."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

logger = logging.getLogger(__name__)


class PDFCPUError(Exception):
    """Base exception for pdfcpu related errors."""

    pass


class PDFCPUNotFoundError(PDFCPUError):
    """Raised when pdfcpu is not found on the system."""

    pass


class PDFCPUExecutionError(PDFCPUError):
    """Raised when pdfcpu execution fails."""

    def __init__(self, message: str, returncode: int, stderr: str = "") -> None:
        """Initialize the error with execution details.

        Args:
            message: Error message.
            returncode: The return code from the process.
            stderr: Standard error output from the process.
        """
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class PDFFormNotFoundError(PDFCPUError):
    """Raised when the PDF does not contain any forms."""

    pass


class FormValidationError(PDFCPUError):
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


class FieldNotFoundError(PDFCPUError):
    """Raised when a field is not found in the form."""

    pass


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

    This Pydantic model combines form field data from pdfcpu with geometry
    information extracted from the PDF.

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
        raw_data: The raw JSON data from pdfcpu.
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
            raw_data: The raw JSON data from pdfcpu.
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
    """Extracts form information from PDF files using pdfcpu.

    This class provides methods to extract form data from PDF files.
    It wraps the pdfcpu command-line tool and provides a Pythonic interface.

    Geometry extraction is automatically performed if pymupdf or pdfplumber
    is available. You can control this behavior with the `geometry_backend`
    parameter.

    Example:
        >>> extractor = PDFFormExtractor()
        >>> form_data = extractor.extract("form.pdf")
        >>> for field in form_data.fields:
        ...     print(f"{field.name}: {field.value}")
        ...     if field.geometry:
        ...         print(f"  Position: ({field.geometry.x}, {field.geometry.y})")

    Raises:
        PDFCPUNotFoundError: If pdfcpu is not installed on the system.
    """

    def __init__(
        self,
        pdfcpu_path: str | None = None,
        timeout_seconds: float = 30.0,
        geometry_backend: str = "auto",
    ) -> None:
        """Initialize the extractor.

        Args:
            pdfcpu_path: Optional path to the pdfcpu executable.
                        If not provided, searches in system PATH.
            timeout_seconds: Timeout for pdfcpu command execution.
            geometry_backend: Geometry extraction backend to use.
                Options: "auto" (try all available), "pymupdf", "pdfplumber", "none".

        Raises:
            PDFCPUNotFoundError: If pdfcpu is not found on the system.
        """
        resolved_path = pdfcpu_path or self._find_pdfcpu()
        if not resolved_path:
            raise PDFCPUNotFoundError(
                "pdfcpu not found. Please install pdfcpu: https://pdfcpu.io/install"
            )
        self._pdfcpu_path: str = resolved_path
        self._timeout_seconds: float = timeout_seconds
        self._geometry_backend: str = geometry_backend

    @staticmethod
    def _find_pdfcpu() -> str | None:
        """Find the pdfcpu executable in the system PATH.

        Returns:
            Path to pdfcpu executable, or None if not found.
        """
        pdfcpu = shutil.which("pdfcpu")
        return pdfcpu

    def _run_command(
        self, args: Sequence[str], check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Run a pdfcpu command.

        Args:
            args: Command arguments.
            check: Whether to check the return code.

        Returns:
            The completed process.

        Raises:
            PDFCPUExecutionError: If the command fails.
            PDFCPUNotFoundError: If pdfcpu is not found.
        """
        cmd: list[str] = [self._pdfcpu_path, *args]
        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=self._timeout_seconds,
            )
            if check and result.returncode != 0:
                stderr_msg = self._sanitize_stderr(result.stderr)
                raise PDFCPUExecutionError(
                    "pdfcpu command failed",
                    result.returncode,
                    stderr_msg,
                )
            return result
        except FileNotFoundError as e:
            raise PDFCPUNotFoundError(f"pdfcpu not found at {self._pdfcpu_path}") from e
        except subprocess.TimeoutExpired as e:
            raise PDFCPUExecutionError(
                f"pdfcpu command timed out after {self._timeout_seconds:.1f}s",
                -1,
                self._sanitize_stderr(e.stderr),
            ) from e

    @staticmethod
    def _sanitize_stderr(stderr: str | bytes | None) -> str:
        """Return a bounded stderr string suitable for end-user messages."""
        if stderr is None:
            return ""
        text = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
        return text.strip()[:500]

    @contextmanager
    def _temporary_json_path(self) -> Iterator[Path]:
        """Create a temporary JSON path and ensure cleanup."""
        with tempfile.TemporaryDirectory(prefix="privacyforms_pdf_") as tmp_dir:
            yield Path(tmp_dir) / "form.json"

    def check_pdfcpu(self) -> bool:
        """Check if pdfcpu is available and working.

        Returns:
            True if pdfcpu is available, False otherwise.
        """
        try:
            result = self._run_command(["version"], check=False)
            return result.returncode == 0 and "pdfcpu" in result.stdout
        except PDFCPUError:
            return False

    def get_pdfcpu_version(self) -> str:
        """Get the installed pdfcpu version.

        Returns:
            The version string of pdfcpu.

        Raises:
            PDFCPUExecutionError: If the version command fails.
        """
        result = self._run_command(["version"])
        return result.stdout.strip()

    def has_form(self, pdf_path: str | Path) -> bool:
        """Check if a PDF contains a form.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            True if the PDF contains a form, False otherwise.

        Raises:
            PDFCPUExecutionError: If the pdfcpu command fails.
        """
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        result = self._run_command(["info", str(pdf_path)], check=False)
        if result.returncode != 0:
            raise PDFCPUExecutionError(
                f"Failed to get PDF info for {pdf_path}",
                result.returncode,
                result.stderr,
            )

        return "Form: Yes" in result.stdout

    def extract(self, pdf_path: str | Path) -> PDFFormData:
        """Extract form data from a PDF file.

        This method exports the form data from the PDF using pdfcpu and
        parses it into a structured format. If a geometry backend is available,
        field positions and sizes will also be extracted.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            PDFFormData containing all form information with PDFField objects.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            PDFCPUExecutionError: If pdfcpu fails to process the PDF.
            PDFFormNotFoundError: If the PDF does not contain a form.
        """
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        # Check if PDF has a form
        if not self.has_form(pdf_path):
            raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

        # Extract geometry if a backend is available
        geometry_map: dict[str, FieldGeometry] = {}
        if self._geometry_backend != "none":
            try:
                geometry_map = self._extract_geometry(pdf_path)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Geometry extraction failed: {e}")

        with self._temporary_json_path() as tmp_path:
            # Export form data using pdfcpu
            result = self._run_command(
                ["form", "export", str(pdf_path), str(tmp_path)],
                check=False,
            )
            if result.returncode != 0:
                raise PDFCPUExecutionError(
                    f"Failed to export form data from {pdf_path}",
                    result.returncode,
                    self._sanitize_stderr(result.stderr),
                )

            # Read and parse the exported JSON
            with open(tmp_path, encoding="utf-8") as f:
                raw_data: dict[str, Any] = json.load(f)

            return self._parse_form_data(pdf_path, raw_data, geometry_map)

    def _extract_geometry(self, pdf_path: Path) -> dict[str, FieldGeometry]:
        """Extract field geometry using available backends.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Dictionary mapping field names to FieldGeometry.
        """
        pdf_bytes = pdf_path.read_bytes()

        if self._geometry_backend == "auto":
            # Try backends in order of preference
            for backend_name, extractor in _GEOMETRY_BACKENDS.items():
                try:
                    return extractor(pdf_bytes)
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"Backend {backend_name} failed: {e}")
                    continue
            return {}
        elif self._geometry_backend in _GEOMETRY_BACKENDS:
            return _GEOMETRY_BACKENDS[self._geometry_backend](pdf_bytes)
        else:
            logger.warning(f"Unknown geometry backend: {self._geometry_backend}")
            return {}

    def extract_to_json(self, pdf_path: str | Path, output_path: str | Path) -> None:
        """Extract form data and save it to a JSON file.

        The output JSON will contain the unified PDFField representation
        with geometry information if available.

        Args:
            pdf_path: Path to the PDF file.
            output_path: Path where the JSON output should be saved.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            PDFCPUExecutionError: If pdfcpu fails to process the PDF.
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
            PDFCPUExecutionError: If pdfcpu fails to process the PDF.
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
            PDFCPUExecutionError: If pdfcpu fails to process the PDF.
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
            PDFCPUExecutionError: If pdfcpu fails to process the PDF.
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
            PDFCPUExecutionError: If pdfcpu fails to process the PDF.
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
            PDFCPUExecutionError: If pdfcpu fails to process the PDF.
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

    def _convert_to_pdfcpu_format(
        self, pdf_path: str | Path, form_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert simple key:value format to pdfcpu export format.

        This is an internal helper method used by fill_form.

        Args:
            pdf_path: Path to the PDF file.
            form_data: Simple format data {"Field Name": value}.

        Returns:
            pdfcpu format data structure.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            PDFFormNotFoundError: If the PDF does not contain a form.
            PDFCPUExecutionError: If pdfcpu fails to process the PDF.
        """
        # Get form fields to determine field types
        form_data_obj = self.extract(pdf_path)

        # Build lookup by field name
        fields_by_name = {f.name: f for f in form_data_obj.fields}

        # Initialize pdfcpu format structure
        pdfcpu_data: dict[str, Any] = {
            "header": {
                "source": str(pdf_path),
                "version": "pdfcpu",
            },
            "forms": [
                {
                    "textfield": [],
                    "datefield": [],
                    "checkbox": [],
                    "radiobuttongroup": [],
                    "combobox": [],
                    "listbox": [],
                }
            ],
        }

        form = pdfcpu_data["forms"][0]

        for field_name, value in form_data.items():
            field = fields_by_name.get(field_name)
            if not field:
                continue  # Skip unknown fields, validation will catch them

            field_entry = {
                "pages": field.pages,
                "id": field.id,
                "name": field.name,
                "value": value,
                "locked": False,
            }

            # Add type-specific attributes
            if field.field_type == "datefield":
                field_entry["format"] = field.format or "yyyy-m-d"  # Default format

            if field.field_type == "radiobuttongroup":
                field_entry["options"] = field.options

            # Add to appropriate list
            form[field.field_type].append(field_entry)

        return pdfcpu_data

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
                        is modified in place (pdfcpu default behavior).
            validate: If True, validates form data before filling.

        Returns:
            Path to the filled PDF (output_path or pdf_path if no output specified).

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            FormValidationError: If validation fails and validate=True.
            PDFCPUExecutionError: If pdfcpu fails to fill the form.
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

        # Convert simple format to pdfcpu format for the fill command
        pdfcpu_data = self._convert_to_pdfcpu_format(pdf_path, form_data)

        with self._temporary_json_path() as tmp_path:
            # Write form data to temporary JSON file
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(pdfcpu_data, f, indent=2)

            # Build command arguments
            args = ["form", "fill", str(pdf_path), str(tmp_path)]
            if output_path:
                args.append(str(output_path))

            # Execute fill command
            result = self._run_command(args, check=False)
            if result.returncode != 0:
                raise PDFCPUExecutionError(
                    f"Failed to fill form in {pdf_path}",
                    result.returncode,
                    self._sanitize_stderr(result.stderr),
                )

            return Path(output_path) if output_path else pdf_path

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
            PDFCPUExecutionError: If pdfcpu fails to fill the form.
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

    def _parse_form_data(
        self,
        pdf_path: Path,
        raw_data: dict[str, Any],
        geometry_map: dict[str, FieldGeometry] | None = None,
    ) -> PDFFormData:
        """Parse raw form data from pdfcpu into structured format.

        Args:
            pdf_path: Path to the PDF file.
            raw_data: Raw JSON data from pdfcpu.
            geometry_map: Optional mapping of field names to geometry.

        Returns:
            Parsed PDFFormData object with PDFField instances.
        """
        header = raw_data.get("header", {})
        pdf_version = header.get("version", "unknown")

        fields: list[PDFField] = []
        geometry_map = geometry_map or {}

        forms = raw_data.get("forms", [])
        if forms:
            form = forms[0]

            # Process each field type
            field_types = [
                "textfield",
                "datefield",
                "checkbox",
                "radiobuttongroup",
                "combobox",
                "listbox",
            ]

            for field_type in field_types:
                for field_data in form.get(field_type, []):
                    field_name = field_data.get("name", "")

                    # Extract type-specific attributes
                    format_str = field_data.get("format") if field_type == "datefield" else None
                    options = (
                        field_data.get("options", [])
                        if field_type in ("radiobuttongroup", "combobox", "listbox")
                        else []
                    )

                    # Get geometry for this field if available
                    geometry = geometry_map.get(field_name)

                    field = PDFField(
                        name=field_name,
                        id=str(field_data.get("id", "")),
                        type=field_type,
                        value=field_data.get("value", ""),
                        pages=field_data.get("pages", []),
                        locked=field_data.get("locked", False),
                        geometry=geometry,
                        format=format_str,
                        options=options if isinstance(options, list) else [],
                    )
                    fields.append(field)

        return PDFFormData(
            source=pdf_path,
            pdf_version=pdf_version,
            has_form=len(fields) > 0,
            fields=fields,
            raw_data=raw_data,
        )


# Geometry extraction backends
_GEOMETRY_BACKENDS: dict[str, callable] = {}  # type: ignore[type-arg]


def _extract_with_pymupdf(pdf_bytes: bytes) -> dict[str, FieldGeometry]:
    """Extract geometry using PyMuPDF (fitz).

    PyMuPDF provides the most accurate and fastest geometry extraction.
    It directly accesses PDF annotation/widget structures.

    Args:
        pdf_bytes: PDF file content.

    Returns:
        Dictionary mapping field names to FieldGeometry.
    """
    import fitz  # pymupdf - optional dependency

    geometry_map: dict[str, FieldGeometry] = {}

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Get all form widgets on this page
            widgets = page.widgets()
            if not widgets:
                continue

            for widget in widgets:
                field_name = widget.field_name
                if not field_name:
                    continue

                # Get bounding rectangle in PDF coordinates
                # fitz.Rect: (x0, y0, x1, y1) where y increases upward
                rect = widget.rect

                geometry_map[field_name] = FieldGeometry(
                    page=page_num + 1,  # Convert 0-based to 1-based
                    rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                )

    return geometry_map


def _extract_with_pdfplumber(pdf_bytes: bytes) -> dict[str, FieldGeometry]:  # pragma: no cover
    """Extract geometry using pdfplumber.

    pdfplumber is a pure-Python alternative that uses pdfminer.six.
    Slower than pymupdf but has MIT license and no compiled dependencies.

    Args:
        pdf_bytes: PDF file content.

    Returns:
        Dictionary mapping field names to FieldGeometry.
    """
    import io

    import pdfplumber  # noqa: F401  # type: ignore[import-not-found]

    geometry_map: dict[str, FieldGeometry] = {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Get form fields from annotations
            annots = page.annots
            if not annots:
                continue

            for annot in annots:
                # Only process Widget annotations (form fields)
                annot_data = annot.get("data", {})
                subtype = annot_data.get("Subtype")
                # Subtype is a PSLiteral, convert to string for comparison
                if str(subtype) != "/'Widget'":
                    continue

                # Get field name from the annotation data
                field_name_bytes = annot_data.get("T")
                if not field_name_bytes:
                    continue

                # Decode field name (it's bytes)
                if isinstance(field_name_bytes, bytes):
                    field_name = field_name_bytes.decode("utf-8", errors="replace")
                else:
                    field_name = str(field_name_bytes)

                if not field_name:
                    continue

                # Get bounding box coordinates from annotation
                # pdfplumber provides x0, y0, x1, y1 directly on the annot
                x0 = annot.get("x0", 0.0)
                y0 = annot.get("y0", 0.0)
                x1 = annot.get("x1", 0.0)
                y1 = annot.get("y1", 0.0)

                geometry_map[field_name] = FieldGeometry(
                    page=page_num,
                    rect=(float(x0), float(y0), float(x1), float(y1)),
                )

    return geometry_map


# Auto-register available backends on module load
try:
    import fitz  # noqa: F401  # optional dependency

    _GEOMETRY_BACKENDS["pymupdf"] = _extract_with_pymupdf
    logger.debug("Registered geometry backend: pymupdf")
except ImportError:
    logger.debug("PyMuPDF (pymupdf) not available for geometry extraction")

try:  # pragma: no cover
    import pdfplumber  # noqa: F401  # type: ignore[import-not-found]

    _GEOMETRY_BACKENDS["pdfplumber"] = _extract_with_pdfplumber
    logger.debug("Registered geometry backend: pdfplumber")
except ImportError:
    logger.debug("pdfplumber not available for geometry extraction")


def get_available_geometry_backends() -> list[str]:
    """Return list of available geometry backends.

    Returns:
        List of backend names that can be used.
    """
    return list(_GEOMETRY_BACKENDS.keys())


def has_geometry_support() -> bool:
    """Check if any geometry extraction backend is available.

    Returns:
        True if at least one backend is installed and available.
    """
    return len(_GEOMETRY_BACKENDS) > 0
