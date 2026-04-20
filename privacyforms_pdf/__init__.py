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
    FieldTextBlock,
    FieldTextDirection,
    FieldTextRole,
    PDFField,
    PDFFieldType,
    PDFPage,
    PDFRepresentation,
    PDFTextBlock,
    RowGroup,
    TextFormat,
)

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
    "FieldTextBlock",
    "FieldTextDirection",
    "FieldTextRole",
    "PDFPage",
    "PDFTextBlock",
    "TextFormat",
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
]
