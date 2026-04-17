"""privacyforms-pdf: Python library for PDF form operations using pypdf."""

from .extractor import (
    FieldNotFoundError,
    FormValidationError,
    PDFFormError,
    PDFFormNotFoundError,
    PDFFormService,
)
from .filler import FormFiller
from .parser import extract_pdf_form, parse_pdf
from .schema import (
    ChoiceOption,
    FieldFlags,
    FieldLayout,
    PDFField,
    PDFFieldType,
    PDFRepresentation,
    RowGroup,
)
from .utils import _install_pypdf_warning_filter, _PypdfWarningFilter

__version__ = "0.2.0"
__all__ = [
    # Main orchestrator
    "PDFFormService",
    # Collaborator classes
    "FormFiller",
    # Canonical schema (new)
    "PDFRepresentation",
    "FieldFlags",
    "FieldLayout",
    "ChoiceOption",
    "RowGroup",
    "PDFFieldType",
    "PDFField",
    # Parser facades
    "parse_pdf",
    "extract_pdf_form",
    # Exceptions
    "PDFFormError",
    "PDFFormNotFoundError",
    "FormValidationError",
    "FieldNotFoundError",
    # Internal helpers (re-exported for tests)
    "_install_pypdf_warning_filter",
    "_PypdfWarningFilter",
]
