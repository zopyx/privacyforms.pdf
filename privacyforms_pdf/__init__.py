"""privacyforms-pdf: Python wrappers for pdfcpu form operations."""

from .extractor import (
    FieldGeometry,
    FieldNotFoundError,
    FormField,
    FormValidationError,
    PDFCPUError,
    PDFCPUExecutionError,
    PDFCPUNotFoundError,
    PDFField,
    PDFFormData,
    PDFFormExtractor,
    PDFFormNotFoundError,
    get_available_geometry_backends,
    has_geometry_support,
)

__version__ = "0.1.2"
__all__ = [
    # Main classes
    "PDFFormExtractor",
    "PDFFormData",
    "PDFField",
    "FieldGeometry",
    # Legacy compatibility
    "FormField",
    # Exceptions
    "PDFCPUError",
    "PDFCPUExecutionError",
    "PDFCPUNotFoundError",
    "PDFFormNotFoundError",
    "FormValidationError",
    "FieldNotFoundError",
    # Utility functions
    "get_available_geometry_backends",
    "has_geometry_support",
]
