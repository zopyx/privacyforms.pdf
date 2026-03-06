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
