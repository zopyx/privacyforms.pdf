"""PDF Form Extractor module using pypdf."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

from privacyforms_pdf.filler import FormFiller
from privacyforms_pdf.models import (
    FieldNotFoundError,
    FormValidationError,
    PDFFormError,
    PDFFormNotFoundError,
)
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
    "FieldNotFoundError",
    "FormValidationError",
    "PDFFormError",
    "PDFFormExtractor",
    "PDFFormNotFoundError",
    "cluster_y_positions",
    "get_available_geometry_backends",
    "has_geometry_support",
    "_install_pypdf_warning_filter",
    "_PypdfWarningFilter",
]


class PDFFormExtractor:
    """Extracts form information from PDF files using pypdf.

    This class provides methods to extract form data from PDF files.
    It uses pypdf for all operations including form extraction and filling.

    Example:
        >>> extractor = PDFFormExtractor()
        >>> has_form = extractor.has_form("form.pdf")
        >>> extractor.fill_form("form.pdf", {"Name": "John"}, "filled.pdf")
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
        self._filler = FormFiller()
        _install_pypdf_warning_filter()

    def has_form(self, pdf_path: str | Path) -> bool:
        """Check if a PDF contains a form."""
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields()
        return fields is not None and len(fields) > 0

    @staticmethod
    def _get_field_type(field: dict[str, Any]) -> str:
        """Determine field type from pypdf field data."""
        from privacyforms_pdf.parser import get_field_type

        return get_field_type(field)

    @staticmethod
    def _get_field_value(field: dict[str, Any]) -> str | bool:
        """Extract value from pypdf field data."""
        value = field.get("/V")
        if value is None:
            return ""
        if isinstance(value, str):
            if value.lower() in ("/yes", "yes", "/on", "on", "1"):
                return True
            elif value.lower() in ("/off", "off", "no", "0"):
                return False
            return value
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
        """Extract options for choice/radio fields."""
        from privacyforms_pdf.parser import get_field_options

        return get_field_options(field)

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
            reader = PdfReader(str(pdf_path))
        except Exception as exc:
            errors.append(f"Could not read PDF: {exc}")
            return errors

        fields = reader.get_fields() or {}
        fields_by_name: dict[str, dict[str, Any]] = dict(fields)

        if not fields_by_name:
            return ["PDF does not contain a form"]

        for field_name, value in form_data.items():
            if not allow_extra_fields and field_name not in fields_by_name:
                errors.append(f"Field not found in form: '{field_name}'")
                continue

            field = fields_by_name.get(field_name)
            field_type = self._get_field_type(field) if field else "textfield"

            if field_type == "checkbox" and not isinstance(value, bool):
                errors.append(
                    f"Field '{field_name}': checkbox value must be boolean, "
                    f"got {type(value).__name__}"
                )

        if strict:
            provided_names = set(form_data.keys())
            for field_name in fields_by_name:
                if field_name not in provided_names:
                    errors.append(f"Required field not provided: '{field_name}'")

        return errors

    def fill_form(
        self,
        pdf_path: str | Path,
        form_data: dict[str, Any],
        output_path: str | Path | None = None,
        *,
        validate: bool = True,
    ) -> Path:
        """Fill a PDF form with data."""
        pdf_path = Path(pdf_path)
        self._validate_pdf_path(pdf_path)

        if not self.has_form(pdf_path):
            raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

        if validate:
            errors = self.validate_form_data(pdf_path, form_data)
            if errors:
                raise FormValidationError("Form data validation failed", errors)

        return self._filler.fill(pdf_path, form_data, output_path, validate=False)

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

    def _validate_pdf_path(self, pdf_path: Path) -> None:
        """Validate that the PDF path exists and is a file."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Path is not a file: {pdf_path}")

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
