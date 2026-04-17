"""Tests for the CLI module.

This module re-exports tests from tests/commands/ for backwards compatibility.
New tests should be added to the appropriate tests/commands/test_pdf_*.py file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from privacyforms_pdf.cli import main
from privacyforms_pdf.commands.utils import create_extractor
from privacyforms_pdf.extractor import PDFFormExtractor

if TYPE_CHECKING:
    from click.testing import CliRunner

# Import all test classes from the commands tests for backwards compatibility
from tests.commands.test_pdf_fill_form import TestFillFormCommand
from tests.commands.test_pdf_info import TestInfoCommand
from tests.commands.test_pdf_parse import TestParseCommand
from tests.commands.test_pdf_verify_data import TestVerifyDataCommand
from tests.commands.test_pdf_verify_json import TestVerifyJsonCommand

# Re-export for backwards compatibility
__all__ = [
    "TestCreateExtractor",
    "TestFillFormCommand",
    "TestInfoCommand",
    "TestMainCommand",
    "TestParseCommand",
    "TestVerifyDataCommand",
    "TestVerifyJsonCommand",
]


class TestMainCommand:
    """Tests for the main CLI group."""

    def test_main_help(self, runner: CliRunner) -> None:
        """Test main command shows help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "PDF Form extraction" in result.output

    def test_main_version(self, runner: CliRunner) -> None:
        """Test main command shows version."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.2.0" in result.output


class TestCreateExtractor:
    """Tests for create_extractor helper."""

    def test_create_extractor_success(self) -> None:
        """Test create_extractor succeeds."""
        extractor = create_extractor()
        assert isinstance(extractor, PDFFormExtractor)

    def test_create_extractor_with_geometry(self) -> None:
        """Test create_extractor with geometry option."""
        extractor = create_extractor(extract_geometry=False)
        assert isinstance(extractor, PDFFormExtractor)
        assert extractor._extract_geometry is False
