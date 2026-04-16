"""PDF Form Extractor module using pypdf."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

from privacyforms_pdf.backends.pdfcpu import (
    PdfcpuBackend,
    PDFCPUError,
    PDFCPUExecutionError,
    PDFCPUNotFoundError,
    is_pdfcpu_available,
)
from privacyforms_pdf.filler import FormFiller
from privacyforms_pdf.models import (
    FieldGeometry,
    FieldNotFoundError,
    FormField,
    FormValidationError,
    PDFField,
    PDFFormData,
    PDFFormError,
    PDFFormNotFoundError,
)
from privacyforms_pdf.reader import FormReader
from privacyforms_pdf.security import PDFSecurityManager
from privacyforms_pdf.utils import (
    _install_pypdf_warning_filter,
    _PypdfWarningFilter,
    cluster_y_positions,
    get_available_geometry_backends,
    has_geometry_support,
)

logger = logging.getLogger(__name__)

# Re-export all public names for backwards compatibility
__all__ = [
    "FieldGeometry",
    "FieldNotFoundError",
    "FormField",
    "FormValidationError",
    "PDFField",
    "PDFFormData",
    "PDFFormError",
    "PDFFormExtractor",
    "PDFFormNotFoundError",
    "PDFCPUError",
    "PDFCPUExecutionError",
    "PDFCPUNotFoundError",
    "cluster_y_positions",
    "get_available_geometry_backends",
    "has_geometry_support",
    "is_pdfcpu_available",
    "_install_pypdf_warning_filter",
    "_PypdfWarningFilter",
]


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
        self._reader = FormReader(extract_geometry=extract_geometry)
        self._filler = FormFiller()
        self._pdfcpu = PdfcpuBackend(timeout_seconds=timeout_seconds)
        self._security = PDFSecurityManager(timeout_seconds=timeout_seconds)
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
        """Determine field type from pypdf field data."""
        return FormReader.get_field_type(field)

    @staticmethod
    def _get_field_value(field: dict[str, Any]) -> str | bool:
        """Extract value from pypdf field data."""
        return FormReader.get_field_value(field)

    @staticmethod
    def _get_field_options(field: dict[str, Any]) -> list[str]:
        """Extract options for choice/radio fields."""
        return FormReader.get_field_options(field)

    def has_form(self, pdf_path: str | Path) -> bool:
        """Check if a PDF contains a form."""
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields()
        return fields is not None and len(fields) > 0

    _DEFAULT_ROW_GAP_THRESHOLD = 15.0

    def _compute_and_set_row_clusters(self, fields: list[PDFField]) -> None:
        """Compute row clusters and set row_y on each field's geometry."""
        self._reader.compute_and_set_row_clusters(fields)

    def _sort_fields(self, fields: list[PDFField]) -> list[PDFField]:
        """Sort fields by page number and position."""
        return self._reader.sort_fields(fields)

    def extract(self, pdf_path: str | Path) -> PDFFormData:
        """Extract form data from a PDF file."""
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)
        return self._reader.read(pdf_path)

    def _get_field_pages(self, reader: PdfReader, field_name: str) -> list[int]:
        """Find which pages contain the field widget (legacy)."""
        widget_info = self._reader.extract_widgets_info(reader)
        return widget_info.get(field_name, ([1], None))[0]

    def _extract_geometry_from_pdf(self, reader: PdfReader) -> dict[str, FieldGeometry]:
        """Extract field geometry from PDF using pypdf (legacy)."""
        widget_info = self._reader.extract_widgets_info(reader)
        return {name: info[1] for name, info in widget_info.items() if info[1] is not None}

    def _extract_widgets_info(
        self, reader: PdfReader
    ) -> dict[str, tuple[list[int], FieldGeometry | None]]:
        """Scan all pages once to find widget pages and geometry."""
        return self._reader.extract_widgets_info(reader)

    def _build_raw_data_structure(self, fields: list[PDFField], source: str) -> dict[str, Any]:
        """Build raw data structure for export."""
        return self._reader.build_raw_data_structure(fields, source)

    def extract_to_json(self, pdf_path: str | Path, output_path: str | Path) -> None:
        """Extract form data and save it to a JSON file."""
        pdf_path = Path(pdf_path)
        output_path = Path(output_path)
        self._validate_pdf_path(pdf_path)

        form_data = self.extract(pdf_path)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(form_data.to_dict(), f, indent=2)

    def list_fields(self, pdf_path: str | Path) -> list[PDFField]:
        """List all form fields in a PDF."""
        form_data = self.extract(pdf_path)
        return form_data.fields

    def get_field_value(self, pdf_path: str | Path, field_name: str) -> str | bool | None:
        """Get the value of a specific form field."""
        fields = self.list_fields(pdf_path)
        for field in fields:
            if field.name == field_name:
                return field.value
        return None

    def get_field_by_id(self, pdf_path: str | Path, field_id: str) -> PDFField | None:
        """Get a form field by its ID."""
        fields = self.list_fields(pdf_path)
        for field in fields:
            if field.id == field_id:
                return field
        return None

    def get_field_by_name(self, pdf_path: str | Path, field_name: str) -> PDFField | None:
        """Get a form field by its name."""
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
        """Validate form data against PDF form fields."""
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        errors: list[str] = []

        try:
            form_data_obj = self.extract(pdf_path)
        except PDFFormNotFoundError:
            return ["PDF does not contain a form"]

        fields_by_name = {f.name: f for f in form_data_obj.fields}

        for field_name, value in form_data.items():
            if not allow_extra_fields and field_name not in fields_by_name:
                errors.append(f"Field not found in form: '{field_name}'")
                continue

            field = fields_by_name.get(field_name)

            if field and field.field_type == "checkbox" and not isinstance(value, bool):
                errors.append(
                    f"Field '{field_name}': checkbox value must be boolean, "
                    f"got {type(value).__name__}"
                )

        if strict:
            provided_names = set(form_data.keys())
            for field in form_data_obj.fields:
                if field.name not in provided_names:
                    errors.append(f"Required field not provided: '{field.name}'")

        return errors

    @staticmethod
    def _should_fallback_from_pdfcpu(error_message: str) -> bool:
        """Return True for known pdfcpu form-compatibility failures."""
        return PdfcpuBackend._should_fallback(error_message)

    def fill_form(
        self,
        pdf_path: str | Path,
        form_data: dict[str, Any],
        output_path: str | Path | None = None,
        *,
        validate: bool = True,
    ) -> Path:
        """Fill a PDF form with data."""
        self._last_fill_backend = "pypdf"
        self._last_fill_backend_reason = None
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        if not self.has_form(pdf_path):
            raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

        if validate:
            errors = self.validate_form_data(pdf_path, form_data)
            if errors:
                raise FormValidationError("Form data validation failed", errors)

        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields() or {}
        writer = PdfWriter()
        writer.append(reader)

        field_values: dict[str, str] = {}
        radio_field_values: dict[str, str] = {}
        listbox_field_values: dict[str, str] = {}
        for field_name, value in form_data.items():
            str_value = ("/Yes" if value else "/Off") if isinstance(value, bool) else str(value)
            field_values[field_name] = str_value
            field_type = self._get_field_type(fields.get(field_name, {}))
            if field_type == "radiobuttongroup":
                radio_field_values[field_name] = str_value
            elif field_type == "listbox":
                listbox_field_values[field_name] = str_value

        if field_values:
            try:
                for page in writer.pages:
                    writer.update_page_form_field_values(page, field_values)
            except AttributeError as exc:
                if "'int' object has no attribute 'encode'" not in str(exc):
                    raise
                self._fill_form_fields_without_appearance(writer, field_values)
            if radio_field_values:
                self._sync_radio_button_states(writer, radio_field_values)
            if listbox_field_values:
                self._sync_listbox_selection_indexes(writer, listbox_field_values)

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
        self._filler._fill_form_fields_without_appearance(writer, field_values)

    def get_field_by_name_from_writer(
        self,
        writer: PdfWriter,
        field_name: str,
    ) -> dict[str, Any] | None:
        """Find a field annotation by name in writer pages."""
        return self._filler.get_field_by_name_from_writer(writer, field_name)

    @staticmethod
    def _get_widget_annotation(
        annotation_ref: Any,
    ) -> tuple[Any, Any]:
        """Resolve widget and parent annotations."""
        return FormFiller._get_widget_annotation(annotation_ref)

    @staticmethod
    def _get_widget_on_state(annotation: dict[str, Any]) -> str | None:
        """Return the non-Off appearance state for a widget, if any."""
        return FormFiller._get_widget_on_state(annotation)

    @classmethod
    def _resolve_radio_field_state(
        cls,
        parent_annotation: dict[str, Any],
        value: str,
    ) -> str:
        """Resolve the selected on-state name for a radio group."""
        return FormFiller._resolve_radio_field_state(parent_annotation, value)

    def _sync_radio_button_states(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Update radio widget appearances to match the selected option."""
        self._filler._sync_radio_button_states(writer, field_values)

    @staticmethod
    def _resolve_listbox_index(parent_annotation: dict[str, Any], value: str) -> int | None:
        """Resolve the selected index for a listbox value."""
        return FormFiller._resolve_listbox_index(parent_annotation, value)

    def _sync_listbox_selection_indexes(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Update listbox values and selection indexes for viewer highlighting."""
        self._filler._sync_listbox_selection_indexes(writer, field_values)

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        """Escape text for use in a PDF string literal."""
        return FormFiller._escape_pdf_text(value)

    def _build_listbox_appearance_stream(
        self,
        writer: PdfWriter,
        annotation: dict[str, Any],
        parent_annotation: dict[str, Any],
        selected_index: int | None,
    ) -> Any | None:
        """Build a listbox appearance stream with highlighted selection."""
        return self._filler._build_listbox_appearance_stream(
            writer, annotation, parent_annotation, selected_index
        )

    def fill_form_from_json(
        self,
        pdf_path: str | Path,
        json_path: str | Path,
        output_path: str | Path | None = None,
        *,
        validate: bool = True,
    ) -> Path:
        """Fill a PDF form with data from a JSON file."""
        pdf_path = Path(pdf_path)
        json_path = Path(json_path)

        self._validate_pdf_path(pdf_path)
        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        if not json_path.is_file():
            raise FileNotFoundError(f"Path is not a file: {json_path}")

        with open(json_path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        return self.fill_form(pdf_path, data, output_path, validate=validate)

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
        return self._pdfcpu._export_form_data(pdf_path, pdfcpu_binary)

    @staticmethod
    def _build_pdfcpu_field_index(
        pdfcpu_data: dict[str, Any],
    ) -> tuple[dict[str, tuple[str, dict[str, Any]]], dict[str, tuple[str, dict[str, Any]]]]:
        """Index exported pdfcpu fields by exact and terminal field name."""
        return PdfcpuBackend._build_field_index(pdfcpu_data)

    def _merge_pdfcpu_form_data(
        self,
        pdfcpu_data: dict[str, Any],
        form_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge simple key:value form data into exported pdfcpu JSON."""
        return self._pdfcpu._merge_form_data(pdfcpu_data, form_data)

    def fill_form_with_pdfcpu(
        self,
        pdf_path: str | Path,
        form_data: dict[str, Any],
        output_path: str | Path | None = None,
        *,
        validate: bool = True,
        pdfcpu_path: str = "pdfcpu",
    ) -> Path:
        """Fill a PDF form with data using pdfcpu."""
        import tempfile

        self._last_fill_backend = "pdfcpu"
        self._last_fill_backend_reason = None
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        pdfcpu_binary = shutil.which(pdfcpu_path)
        if pdfcpu_binary is None:
            raise PDFFormError(
                f"pdfcpu binary not found: {pdfcpu_path}. "
                "Please install pdfcpu: https://pdfcpu.io/install"
            )

        if not self.has_form(pdf_path):
            raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

        if validate:
            errors = self.validate_form_data(pdf_path, form_data)
            if errors:
                raise FormValidationError("Form data validation failed", errors)

        output_file = Path(output_path) if output_path else pdf_path

        try:
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

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as temp_json:
            json.dump(pdfcpu_json_data, temp_json, indent=2)
            temp_json_path = Path(temp_json.name)

        try:
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

            if not output_file.exists():
                raise PDFFormError(f"pdfcpu did not create output file: {output_file}")

            return output_file

        finally:
            if temp_json_path.exists():
                temp_json_path.unlink()

    def _validate_pdf_path(self, pdf_path: Path) -> None:
        """Validate that the PDF path exists and is a file."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Path is not a file: {pdf_path}")

    def encrypt(
        self,
        pdf_path: str | Path,
        output_path: str | Path | None = None,
        *,
        owner_password: str,
        user_password: str | None = None,
        mode: str = "aes",
        key_length: str = "256",
        permissions: str = "none",
    ) -> Path:
        """Encrypt a PDF file.

        Args:
            pdf_path: Path to the PDF file to encrypt.
            output_path: Optional output path. If not provided, modifies input.
            owner_password: Owner password (mandatory).
            user_password: Optional user password.
            mode: Encryption algorithm ("rc4" or "aes", default: "aes").
            key_length: Key length in bits ("40", "128", or "256", default: "256").
            permissions: Permission preset ("none" or "all", default: "none").

        Returns:
            Path to the encrypted PDF.
        """
        return self._security.encrypt(
            pdf_path,
            output_path,
            owner_password=owner_password,
            user_password=user_password,
            mode=mode,
            key_length=key_length,
            permissions=permissions,
        )

    def set_permissions(
        self,
        pdf_path: str | Path,
        *,
        owner_password: str,
        user_password: str | None = None,
        permissions_preset: str | None = None,
        print_perm: bool = False,
        modify: bool = False,
        extract: bool = False,
        annotations: bool = False,
        fill_forms: bool = False,
        extract_accessibility: bool = False,
        assemble: bool = False,
        print_high: bool = False,
        custom_bits: str | None = None,
    ) -> None:
        """Set permissions of an encrypted PDF file.

        Args:
            pdf_path: Path to the encrypted PDF file.
            owner_password: Owner password (required).
            user_password: Optional user password.
            permissions_preset: Preset ("none", "print", or "all").
            print_perm: Allow printing.
            modify: Allow modification.
            extract: Allow text/graphics extraction.
            annotations: Allow adding/modifying annotations.
            fill_forms: Allow filling form fields.
            extract_accessibility: Allow extraction for accessibility.
            assemble: Allow document assembly.
            print_high: Allow high-quality printing.
            custom_bits: Custom permission bits in hex or binary.
        """
        self._security.set_permissions(
            pdf_path,
            owner_password=owner_password,
            user_password=user_password,
            permissions_preset=permissions_preset,
            print_perm=print_perm,
            modify=modify,
            extract=extract,
            annotations=annotations,
            fill_forms=fill_forms,
            extract_accessibility=extract_accessibility,
            assemble=assemble,
            print_high=print_high,
            custom_bits=custom_bits,
        )

    def list_permissions(
        self,
        pdf_path: str | Path,
        *,
        user_password: str | None = None,
        owner_password: str | None = None,
    ) -> dict[str, Any]:
        """List permissions of an encrypted PDF file.

        Args:
            pdf_path: Path to the PDF file.
            user_password: Optional user password.
            owner_password: Optional owner password.

        Returns:
            Structured dictionary with permission information.
        """
        return self._security.list_permissions(
            pdf_path,
            user_password=user_password,
            owner_password=owner_password,
        )
