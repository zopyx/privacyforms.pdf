"""PDF Form Extractor module using pdfcpu."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


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


@dataclass(frozen=True)
class FormField:
    """Represents a single form field.

    Attributes:
        field_type: The type of the form field (e.g., 'textfield', 'checkbox').
        pages: List of pages where this field appears.
        id: The unique identifier of the field.
        name: The name of the field.
        value: The current value of the field.
        locked: Whether the field is locked.
    """

    field_type: str
    pages: list[int]
    id: str
    name: str
    value: str | bool
    locked: bool


@dataclass(frozen=True)
class PDFFormData:
    """Represents extracted PDF form data.

    Attributes:
        source: Path to the source PDF file.
        pdf_version: Version of the PDF.
        has_form: Whether the PDF contains a form.
        fields: List of form fields.
        raw_data: The raw JSON data from pdfcpu.
    """

    source: Path
    pdf_version: str
    has_form: bool
    fields: list[FormField]
    raw_data: dict[str, Any]


class PDFFormExtractor:
    """Extracts form information from PDF files using pdfcpu.

    This class provides methods to extract form data from PDF files.
    It wraps the pdfcpu command-line tool and provides a Pythonic interface.

    Example:
        >>> extractor = PDFFormExtractor()
        >>> form_data = extractor.extract("form.pdf")
        >>> for field in form_data.fields:
        ...     print(f"{field.name}: {field.value}")

    Raises:
        PDFCPUNotFoundError: If pdfcpu is not installed on the system.
    """

    def __init__(self, pdfcpu_path: str | None = None) -> None:
        """Initialize the extractor.

        Args:
            pdfcpu_path: Optional path to the pdfcpu executable.
                        If not provided, searches in system PATH.

        Raises:
            PDFCPUNotFoundError: If pdfcpu is not found on the system.
        """
        resolved_path = pdfcpu_path or self._find_pdfcpu()
        if not resolved_path:
            raise PDFCPUNotFoundError(
                "pdfcpu not found. Please install pdfcpu: https://pdfcpu.io/install"
            )
        self._pdfcpu_path: str = resolved_path

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
            )
            if check and result.returncode != 0:
                stderr_msg = result.stderr if result.stderr else ""
                raise PDFCPUExecutionError(
                    f"pdfcpu command failed: {' '.join(cmd)}",
                    result.returncode,
                    stderr_msg,
                )
            return result
        except FileNotFoundError as e:
            raise PDFCPUNotFoundError(f"pdfcpu not found at {self._pdfcpu_path}") from e

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
        parses it into a structured format.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            PDFFormData containing all form information.

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

        # Export form data to a temporary JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Export form data using pdfcpu
            result = self._run_command(
                ["form", "export", str(pdf_path), str(tmp_path)],
                check=False,
            )
            if result.returncode != 0:
                raise PDFCPUExecutionError(
                    f"Failed to export form data from {pdf_path}",
                    result.returncode,
                    result.stderr,
                )

            # Read and parse the exported JSON
            with open(tmp_path, encoding="utf-8") as f:
                raw_data: dict[str, Any] = json.load(f)

            return self._parse_form_data(pdf_path, raw_data)

        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()

    def extract_to_json(self, pdf_path: str | Path, output_path: str | Path) -> None:
        """Extract form data and save it to a JSON file.

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

        result = self._run_command(
            ["form", "export", str(pdf_path), str(output_path)],
            check=False,
        )
        if result.returncode != 0:
            raise PDFCPUExecutionError(
                f"Failed to export form data from {pdf_path}",
                result.returncode,
                result.stderr,
            )

    def list_fields(self, pdf_path: str | Path) -> list[FormField]:
        """List all form fields in a PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of FormField objects.

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

    def get_field_by_id(self, pdf_path: str | Path, field_id: str) -> FormField | None:
        """Get a form field by its ID.

        Args:
            pdf_path: Path to the PDF file.
            field_id: ID of the field to retrieve.

        Returns:
            The FormField object, or None if the field is not found.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            PDFCPUExecutionError: If pdfcpu fails to process the PDF.
        """
        fields = self.list_fields(pdf_path)
        for field in fields:
            if field.id == field_id:
                return field
        return None

    def get_field_by_name(self, pdf_path: str | Path, field_name: str) -> FormField | None:
        """Get a form field by its name.

        Args:
            pdf_path: Path to the PDF file.
            field_name: Name of the field to retrieve.

        Returns:
            The FormField object, or None if the field is not found.

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

        This method validates that the provided form data matches the structure
        and field types of the PDF form. It checks:
        - All referenced fields exist in the form
        - Field value types match expected types
        - Required fields have values (when strict=True)

        Args:
            pdf_path: Path to the PDF file.
            form_data: The form data to validate (must match export format).
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

        # Build lookup maps
        fields_by_id = {f.id: f for f in form_data_obj.fields}
        fields_by_name = {f.name: f for f in form_data_obj.fields}

        # Extract fields from input data
        input_fields: dict[str, dict[str, Any]] = {}
        forms = form_data.get("forms", [])
        if forms and isinstance(forms, list):
            form = forms[0]
            field_types = [
                "textfield",
                "datefield",
                "checkbox",
                "radiobuttongroup",
                "combobox",
                "listbox",
            ]
            for field_type in field_types:
                for field in form.get(field_type, []):
                    field_id = field.get("id")
                    field_name = field.get("name")
                    key = field_id or field_name
                    if key:
                        input_fields[key] = {
                            "type": field_type,
                            "id": field_id,
                            "name": field_name,
                            "value": field.get("value"),
                            "locked": field.get("locked"),
                        }

        # Validate each input field exists in form
        if not allow_extra_fields:
            for key, field_info in input_fields.items():
                if key not in fields_by_id and key not in fields_by_name:
                    field_name = field_info.get("name")
                    field_id = field_info.get("id")
                    if field_name and field_id:
                        errors.append(
                            f"Field not found in form: '{field_name}' (id: {field_id})"
                        )
                    elif field_name:
                        errors.append(f"Field not found in form: '{field_name}'")
                    else:
                        errors.append(f"Field not found in form: id '{field_id}'")
                    continue

                # Validate value type matches field type
                pdf_field = fields_by_id.get(key) or fields_by_name.get(key)
                if pdf_field:
                    value = field_info["value"]
                    if pdf_field.field_type == "checkbox" and not isinstance(value, bool):
                        field_label = field_info.get("name") or key
                        errors.append(
                            f"Field '{field_label}': checkbox value must be boolean, "
                            f"got {type(value).__name__}"
                        )

        # In strict mode, check all form fields are provided
        if strict:
            provided_keys = set(input_fields.keys())
            for field in form_data_obj.fields:
                if field.id not in provided_keys and field.name not in provided_keys:
                    errors.append(f"Required field not provided: '{field.name}' (id: {field.id})")

        return errors

    def _is_simple_format(self, form_data: dict[str, Any]) -> bool:
        """Check if form_data is in simple key:value format.

        Simple format: {"Field Name": "value", "Checkbox": true}
        pdfcpu format: {"forms": [{"textfield": [...]}]}

        Args:
            form_data: The form data to check.

        Returns:
            True if simple format, False if pdfcpu format.
        """
        if not form_data:
            return True  # Empty dict is considered simple format
        # If it has "forms" key with list value, it's pdfcpu format
        return not ("forms" in form_data and isinstance(form_data["forms"], list))

    def _convert_simple_to_pdfcpu_format(
        self, pdf_path: str | Path, simple_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert simple key:value format to pdfcpu export format.

        Args:
            pdf_path: Path to the PDF file.
            simple_data: Simple format data {"Field Name": value}.

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

        for field_name, value in simple_data.items():
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
                field_entry["format"] = "yyyy-m-d"  # Default format

            if field.field_type == "radiobuttongroup":
                field_entry["options"] = getattr(field, "options", [])

            # Add to appropriate list
            form[field.field_type].append(field_entry)

        return pdfcpu_data

    def validate_simple_form_data(
        self,
        pdf_path: str | Path,
        simple_data: dict[str, Any],
        *,
        strict: bool = False,
        allow_extra_fields: bool = False,
    ) -> list[str]:
        """Validate simple key:value format form data.

        Args:
            pdf_path: Path to the PDF file.
            simple_data: Simple format data {"Field Name": value}.
            strict: If True, also checks that all form fields are provided.
            allow_extra_fields: If True, allows fields not present in the form.

        Returns:
            List of validation error messages (empty if valid).
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
            for field_name, value in simple_data.items():
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
            provided_names = set(simple_data.keys())
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
        """Fill a PDF form with data from a JSON structure.

        This method accepts data in two formats:
        1. Simple key:value format: {"Field Name": "value", "Checkbox": true}
        2. pdfcpu export format: {"forms": [{"textfield": [...]}]}

        Args:
            pdf_path: Path to the PDF file containing the form.
            form_data: The form data to fill (simple format or pdfcpu format).
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
            >>> # Simple format
            >>> form_data = {"Candidate Name": "John Smith", "Full time": True}
            >>> extractor.fill_form("form.pdf", form_data, "filled.pdf")

            >>> # pdfcpu format
            >>> form_data = {
            ...     "forms": [{
            ...         "textfield": [
            ...             {"name": "firstName", "value": "John", "locked": False}
            ...         ]
            ...     }]
            ... }
            >>> extractor.fill_form("form.pdf", form_data, "filled.pdf")
        """
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        # Check if PDF has a form
        if not self.has_form(pdf_path):
            raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

        # Detect format and convert if necessary
        is_simple = self._is_simple_format(form_data)

        # Validate form data if requested
        if validate:
            if is_simple:
                errors = self.validate_simple_form_data(pdf_path, form_data)
            else:
                errors = self.validate_form_data(pdf_path, form_data)
            if errors:
                raise FormValidationError("Form data validation failed", errors)

        # Convert simple format to pdfcpu format if needed
        if is_simple:
            form_data = self._convert_simple_to_pdfcpu_format(pdf_path, form_data)

        # Write form data to temporary JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(form_data, tmp, indent=2)
            tmp_path = Path(tmp.name)

        try:
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
                    result.stderr,
                )

            return Path(output_path) if output_path else pdf_path

        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()

    def fill_form_from_json(
        self,
        pdf_path: str | Path,
        json_path: str | Path,
        output_path: str | Path | None = None,
        *,
        validate: bool = True,
    ) -> Path:
        """Fill a PDF form with data from a JSON file.

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

    def _parse_form_data(self, pdf_path: Path, raw_data: dict[str, Any]) -> PDFFormData:
        """Parse raw form data from pdfcpu into structured format.

        Args:
            pdf_path: Path to the PDF file.
            raw_data: Raw JSON data from pdfcpu.

        Returns:
            Parsed PDFFormData object.
        """
        header = raw_data.get("header", {})
        pdf_version = header.get("version", "unknown")

        fields: list[FormField] = []

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
                    field = FormField(
                        field_type=field_type,
                        pages=field_data.get("pages", []),
                        id=str(field_data.get("id", "")),
                        name=field_data.get("name", ""),
                        value=field_data.get("value", ""),
                        locked=field_data.get("locked", False),
                    )
                    fields.append(field)

        return PDFFormData(
            source=pdf_path,
            pdf_version=pdf_version,
            has_form=len(fields) > 0,
            fields=fields,
            raw_data=raw_data,
        )
