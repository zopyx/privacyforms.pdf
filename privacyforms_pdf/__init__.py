"""privacyforms-pdf: Python library for PDF form operations using pypdf."""

from .extractor import (
    FieldGeometry,
    FieldNotFoundError,
    FormField,
    FormValidationError,
    # Backwards compatibility aliases (deprecated, will be removed in a future version)
    PDFCPUError,
    PDFCPUExecutionError,
    PDFCPUNotFoundError,
    PDFField,
    PDFFormData,
    PDFFormError,
    PDFFormExtractor,
    PDFFormNotFoundError,
    get_available_geometry_backends,
    has_geometry_support,
)

__version__ = "0.1.3"
__all__ = [
    # Main classes
    "PDFFormExtractor",
    "PDFFormData",
    "PDFField",
    "FieldGeometry",
    # Legacy compatibility
    "FormField",
    # Exceptions
    "PDFFormError",
    "PDFFormNotFoundError",
    "FormValidationError",
    "FieldNotFoundError",
    # Backwards compatibility - old exception names (deprecated)
    "PDFCPUError",
    "PDFCPUExecutionError",
    "PDFCPUNotFoundError",
    # Utility functions
    "get_available_geometry_backends",
    "has_geometry_support",
]
