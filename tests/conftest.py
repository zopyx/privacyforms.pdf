"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_pdf_path() -> str:
    """Provide path to the sample filled PDF."""
    return "samples/FilledForm.pdf"
