"""PDF Form Service module using pypdf."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pypdf import PdfReader, PdfWriter

from privacyforms_pdf.filler import FormFiller
from privacyforms_pdf.json_utils import load_json_object
from privacyforms_pdf.models import (
    FieldNotFoundError,
    FormValidationError,
    PDFFormError,
    PDFFormNotFoundError,
)
from privacyforms_pdf.parser import parse_pdf
from privacyforms_pdf.security_io import safe_write_text, validate_pdf_path
from privacyforms_pdf.utils import (
    _install_pypdf_warning_filter,
    _PypdfWarningFilter,
    cluster_y_positions,
)

if TYPE_CHECKING:
    from privacyforms_pdf.schema import PDFField, PDFRepresentation

logger = logging.getLogger(__name__)

# Public API
__all__ = [
    "FieldNotFoundError",
    "FormValidationError",
    "PDFFormError",
    "PDFFormNotFoundError",
    "PDFFormService",
    "cluster_y_positions",
    "_install_pypdf_warning_filter",
    "_PypdfWarningFilter",
]


class PDFFormService:
    """High-level service for PDF form operations using pypdf.

    Provides methods to parse, validate, and fill PDF forms.

    Example:
        >>> service = PDFFormService()
        >>> has_form = service.has_form("form.pdf")
        >>> service.fill_form("form.pdf", {"Name": "John"}, "filled.pdf")
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
        validate_pdf_path(pdf_path)

        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields()
        return fields is not None and len(fields) > 0

    def extract(
        self,
        pdf_path: str | Path,
        *,
        source: str | None = None,
    ) -> PDFRepresentation:
        """Parse a PDF into the canonical PDFRepresentation."""
        pdf_path = Path(pdf_path)
        validate_pdf_path(pdf_path)
        return parse_pdf(pdf_path, source=source)

    def extract_to_json(
        self,
        pdf_path: str | Path,
        output_path: str | Path,
        *,
        source: str | None = None,
    ) -> None:
        """Write the canonical parsed representation to a JSON file."""
        representation = self.extract(pdf_path, source=source)
        safe_write_text(Path(output_path), representation.to_compact_json(indent=2))

    def list_fields(self, pdf_path: str | Path) -> list[PDFField]:
        """Return parsed fields for the given PDF."""
        representation = self.extract(pdf_path)
        return list(representation.fields)

    def get_field_by_id(self, pdf_path: str | Path, field_id: str) -> PDFField | None:
        """Return a parsed field by canonical field ID."""
        representation = self.extract(pdf_path)
        return representation.get_field_by_id(field_id)

    def get_field_by_name(self, pdf_path: str | Path, field_name: str) -> PDFField | None:
        """Return a parsed field by PDF field name."""
        representation = self.extract(pdf_path)
        return representation.get_field_by_name(field_name)

    def get_field_value(
        self, pdf_path: str | Path, field_name: str
    ) -> str | bool | list[str] | None:
        """Return the current value of a parsed field by name."""
        field = self.get_field_by_name(pdf_path, field_name)
        return None if field is None else field.value

    @classmethod
    def load_form_data_json(cls, json_path: str | Path) -> dict[str, Any]:
        """Load a form-data JSON file with basic size and depth hardening."""
        return load_json_object(json_path)

    @staticmethod
    def get_json_schema() -> dict[str, Any]:
        """Return the JSON Schema for the canonical PDFRepresentation model.

        Returns:
            A dict representing the JSON Schema (draft 2020-12) of
            :class:`~privacyforms_pdf.schema.PDFRepresentation`.
        """
        from privacyforms_pdf.schema import PDFRepresentation

        return PDFRepresentation.model_json_schema()

    def _normalize_form_data_keys(
        self,
        pdf_path: Path,
        form_data: dict[str, Any],
        *,
        key_mode: Literal["name", "id", "auto"],
        representation: PDFRepresentation | None = None,
    ) -> tuple[dict[str, Any], list[str]]:
        """Normalize input data keys to PDF field names."""
        normalized: dict[str, Any] = {}
        errors: list[str] = []

        if key_mode == "name":
            return {str(key): value for key, value in form_data.items()}, errors

        if representation is None:
            representation = self.extract(pdf_path)
        id_to_name = {field.id: field.name for field in representation.fields}
        known_names = {field.name for field in representation.fields}

        for raw_key, value in form_data.items():
            key = str(raw_key)
            if key_mode == "id":
                resolved_key = id_to_name.get(key, key)
            else:
                resolved_key = key if key in known_names else id_to_name.get(key, key)

            if resolved_key in normalized and key != resolved_key:
                errors.append(f"Multiple input keys map to the same form field: '{resolved_key}'")
                continue

            normalized[resolved_key] = value

        return normalized, errors

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
        key_mode: Literal["name", "id", "auto"] = "name",
        reader: PdfReader | None = None,
        representation: PDFRepresentation | None = None,
    ) -> list[str]:
        """Validate form data against PDF form fields."""
        pdf_path = Path(pdf_path)
        validate_pdf_path(pdf_path)

        errors: list[str] = []
        normalized_form_data, normalization_errors = self._normalize_form_data_keys(
            pdf_path,
            form_data,
            key_mode=key_mode,
            representation=representation,
        )
        errors.extend(normalization_errors)

        own_reader = reader is None
        if own_reader:
            try:
                reader = PdfReader(str(pdf_path))
            except Exception as exc:
                errors.append(f"Could not read PDF: {exc}")
                return errors

        assert reader is not None
        fields = reader.get_fields() or {}
        fields_by_name: dict[str, dict[str, Any]] = dict(fields)

        if not fields_by_name:
            return ["PDF does not contain a form"]

        for field_name, value in normalized_form_data.items():
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
            provided_names = set(normalized_form_data.keys())
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
        key_mode: Literal["name", "id", "auto"] = "name",
    ) -> Path:
        """Fill a PDF form with data."""
        pdf_path = Path(pdf_path)
        validate_pdf_path(pdf_path)

        reader = PdfReader(str(pdf_path))
        try:
            fields = reader.get_fields()
            if not fields:
                raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

            representation = parse_pdf(pdf_path, reader=reader)

            normalized_form_data, normalization_errors = self._normalize_form_data_keys(
                pdf_path,
                form_data,
                key_mode=key_mode,
                representation=representation,
            )
            if normalization_errors:
                raise FormValidationError(
                    "Form data key normalization failed", normalization_errors
                )

            if validate:
                errors = self.validate_form_data(
                    pdf_path,
                    form_data,
                    key_mode=key_mode,
                    reader=reader,
                    representation=representation,
                )
                if errors:
                    raise FormValidationError("Form data validation failed", errors)

            return self._filler.fill(pdf_path, normalized_form_data, output_path, reader=reader)
        finally:
            reader.close()

    def fill_form_from_json(
        self,
        pdf_path: str | Path,
        json_path: str | Path,
        output_path: str | Path | None = None,
        *,
        validate: bool = True,
        key_mode: Literal["name", "id", "auto"] = "name",
    ) -> Path:
        """Fill a PDF form with data from a JSON file."""
        pdf_path = Path(pdf_path)
        validate_pdf_path(pdf_path)
        data = self.load_form_data_json(json_path)

        return self.fill_form(
            pdf_path,
            data,
            output_path,
            validate=validate,
            key_mode=key_mode,
        )

    def _fill_form_fields_without_appearance(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Fallback form fill that skips appearance-stream generation.

        Delegates to
        :meth:`~privacyforms_pdf.filler.FormFiller._fill_form_fields_without_appearance`.
        """
        self._filler._fill_form_fields_without_appearance(writer, field_values)

    def get_field_by_name_from_writer(
        self,
        writer: PdfWriter,
        field_name: str,
    ) -> dict[str, Any] | None:
        """Find a field annotation by name in writer pages.

        Searches all pages of the given *writer* for a widget whose qualified
        name, annotation name, or parent name matches *field_name*.

        Delegates to :meth:`~privacyforms_pdf.filler.FormFiller.get_field_by_name_from_writer`.
        """
        return self._filler.get_field_by_name_from_writer(writer, field_name)

    @staticmethod
    def _get_widget_annotation(
        annotation_ref: Any,
    ) -> tuple[Any, Any]:
        """Resolve widget and parent annotations.

        PDF form fields are often split into a "parent" field dictionary (which
        holds the field type, value, and options) and one or more "widget"
        annotations (which hold the visual representation). This helper resolves
        an indirect reference to the widget dictionary and then returns both the
        widget and its parent.

        Delegates to :meth:`~privacyforms_pdf.filler.FormFiller._get_widget_annotation`.
        """
        return FormFiller._get_widget_annotation(annotation_ref)

    @staticmethod
    def _get_widget_on_state(annotation: dict[str, Any]) -> str | None:
        """Return the non-Off appearance state for a widget, if any.

        Looks inside the widget's /AP (appearance dictionary) → /N (normal
        appearance) for state names and returns the first one that is not
        ``/Off``.

        Delegates to :meth:`~privacyforms_pdf.filler.FormFiller._get_widget_on_state`.
        """
        return FormFiller._get_widget_on_state(annotation)

    @classmethod
    def _resolve_radio_field_state(
        cls,
        parent_annotation: dict[str, Any],
        value: str,
    ) -> str:
        """Resolve the selected on-state name for a radio group.

        Maps the logical value (e.g. "Option1") to the exact NameObject state
        string stored in the widget's appearance dictionary. This is necessary
        because different PDF generators use different on-state names.

        Delegates to :meth:`~privacyforms_pdf.filler.FormFiller._resolve_radio_field_state`.
        """
        return FormFiller._resolve_radio_field_state(parent_annotation, value)

    def _sync_radio_button_states(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Update radio widget appearances to match the selected option.

        Iterates over all pages in *writer*, finds radio-button widgets, and
        sets their ``/AS`` (appearance state) and ``/V`` (value) entries so that
        the checked button matches the filled data.

        Delegates to :meth:`~privacyforms_pdf.filler.FormFiller._sync_radio_button_states`.
        """
        self._filler._sync_radio_button_states(writer, field_values)

    @staticmethod
    def _resolve_listbox_index(parent_annotation: dict[str, Any], value: str) -> int | None:
        """Resolve the selected index for a listbox value.

        Matches *value* against the ``/Opt`` array of the listbox field and
        returns the zero-based index of the match, or ``None`` if not found.

        Delegates to :meth:`~privacyforms_pdf.filler.FormFiller._resolve_listbox_index`.
        """
        return FormFiller._resolve_listbox_index(parent_annotation, value)

    def _sync_listbox_selection_indexes(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Update listbox values and selection indexes for viewer highlighting.

        Sets ``/V`` (value), ``/I`` (selected indexes), ``/TI`` (top index), and
        builds a custom appearance stream so that the highlighted row is visible
        in PDF viewers.

        Delegates to :meth:`~privacyforms_pdf.filler.FormFiller._sync_listbox_selection_indexes`.
        """
        self._filler._sync_listbox_selection_indexes(writer, field_values)

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        r"""Escape text for use in a PDF string literal.

        In PDF content streams parentheses delimit text strings, so ``(``, ``)``
        and ``\`` must be backslash-escaped.

        Delegates to :meth:`~privacyforms_pdf.filler.FormFiller._escape_pdf_text`.
        """
        return FormFiller._escape_pdf_text(value)

    def _build_listbox_appearance_stream(
        self,
        writer: PdfWriter,
        annotation: dict[str, Any],
        parent_annotation: dict[str, Any],
        selected_index: int | None,
    ) -> Any | None:
        """Build a listbox appearance stream with highlighted selection.

        Constructs a raw PDF content stream that renders the listbox options,
        drawing a light-blue highlight rectangle behind the selected item so
        that viewers display the filled choice correctly.

        Delegates to :meth:`~privacyforms_pdf.filler.FormFiller._build_listbox_appearance_stream`.
        """
        return self._filler._build_listbox_appearance_stream(
            writer, annotation, parent_annotation, selected_index
        )
