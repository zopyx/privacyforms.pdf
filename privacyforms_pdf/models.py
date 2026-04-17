"""Data models and exceptions for privacyforms-pdf."""

from __future__ import annotations


class PDFFormError(Exception):
    """Base exception for PDF form related errors."""

    pass


class PDFFormNotFoundError(PDFFormError):
    """Raised when the PDF does not contain any forms."""

    pass


class FieldNotFoundError(PDFFormError):
    """Raised when a field is not found in the form."""

    pass


class FormValidationError(PDFFormError):
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
