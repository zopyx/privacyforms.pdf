"""Utility functions for CLI commands."""

from __future__ import annotations

from ..extractor import PDFFormService


def create_extractor(extract_geometry: bool = True) -> PDFFormService:
    """Create a PDFFormService instance, handling errors gracefully.

    Args:
        extract_geometry: Whether to extract field geometry.

    Returns:
        Configured PDFFormService instance.
    """
    # pypdf is always available, no external dependencies to check
    return PDFFormService(extract_geometry=extract_geometry)
