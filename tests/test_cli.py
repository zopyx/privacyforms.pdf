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
from tests.commands.test_pdf_check import TestCheckCommand
from tests.commands.test_pdf_encrypt import TestEncryptCommand
from tests.commands.test_pdf_extract import TestExtractCommand
from tests.commands.test_pdf_fill_form import TestFillFormCommand
from tests.commands.test_pdf_get_value import TestGetValueCommand
from tests.commands.test_pdf_info import TestInfoCommand
from tests.commands.test_pdf_list_fields import TestListFieldsCommand
from tests.commands.test_pdf_list_permissions import (
    TestListPermissionsCommand,
    TestPermissionFormatter,
    TestPermissionParser,
)
from tests.commands.test_pdf_set_permissions import TestSetPermissionsCommand

# Re-export for backwards compatibility
__all__ = [
    "TestCheckCommand",
    "TestCreateExtractor",
    "TestEncryptCommand",
    "TestExtractCommand",
    "TestFillFormCommand",
    "TestGetValueCommand",
    "TestInfoCommand",
    "TestListFieldsCommand",
    "TestListPermissionsCommand",
    "TestMainCommand",
    "TestPermissionFormatter",
    "TestPermissionParser",
    "TestSetPermissionsCommand",
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
        assert "0.1.3" in result.output


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
