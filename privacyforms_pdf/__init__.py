"""privacyforms-pdf: Python library for PDF form operations using pypdf."""

from privacyforms_pdf.reader import FormReader

from .backends.pdfcpu import (
    PDFCPUError,
    PDFCPUExecutionError,
    PDFCPUNotFoundError,
    is_pdfcpu_available,
)
from .extractor import (
    FieldGeometry,
    FieldNotFoundError,
    FormField,
    FormValidationError,
    PDFField,
    PDFFormData,
    PDFFormError,
    PDFFormExtractor,
    PDFFormNotFoundError,
    cluster_y_positions,
    get_available_geometry_backends,
    has_geometry_support,
)
from .filler import FormFiller
from .security import PDFSecurityManager
from .utils import _install_pypdf_warning_filter, _PypdfWarningFilter

__version__ = "0.1.3"
__all__ = [
    # Main orchestrator
    "PDFFormExtractor",
    # Collaborator classes
    "FormReader",
    "FormFiller",
    "PDFSecurityManager",
    # Data models
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
    "is_pdfcpu_available",
    "cluster_y_positions",
    # Internal helpers (re-exported for tests)
    "_install_pypdf_warning_filter",
    "_PypdfWarningFilter",
]
