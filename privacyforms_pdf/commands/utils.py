"""Utility functions for CLI commands."""

from __future__ import annotations

from ..extractor import PDFFormExtractor


def create_extractor(extract_geometry: bool = True) -> PDFFormExtractor:
    """Create a PDFFormExtractor instance, handling errors gracefully.

    Args:
        extract_geometry: Whether to extract field geometry.

    Returns:
        Configured PDFFormExtractor instance.
    """
    # pypdf is always available, no external dependencies to check
    return PDFFormExtractor(extract_geometry=extract_geometry)
