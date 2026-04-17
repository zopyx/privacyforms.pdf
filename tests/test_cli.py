"""Tests for the CLI module.

This module re-exports tests from tests/commands/ for backwards compatibility.
New tests should be added to the appropriate tests/commands/test_pdf_*.py file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from privacyforms_pdf.cli import _is_trusted_plugin, main

if TYPE_CHECKING:
    import pytest
from privacyforms_pdf.commands.utils import create_extractor
from privacyforms_pdf.extractor import PDFFormService

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


class TestPluginTrust:
    """Tests for plugin whitelisting in CLI."""

    def test_trusted_builtin_plugin(self) -> None:
        """A built-in command callback is trusted."""
        import privacyforms_pdf.commands.pdf_info as info_mod

        cmd = info_mod.info_command
        assert _is_trusted_plugin(cmd.callback) is True

    def test_untrusted_plugin_rejected(self) -> None:
        """A callback from an unknown module is not trusted."""

        def evil_callback() -> None:
            pass

        evil_callback.__module__ = "evil_pkg.backdoor"
        assert _is_trusted_plugin(evil_callback) is False

    def test_no_module_attr_rejected(self) -> None:
        """A callback without __module__ is not trusted."""

        class NoModule:
            pass

        assert _is_trusted_plugin(NoModule()) is False

    def test_untrusted_plugins_skipped_at_load(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Untrusted plugins are skipped during CLI load (hits continue branch)."""
        from privacyforms_pdf import cli

        test_group = click.Group("test")
        monkeypatch.setattr(cli, "_is_trusted_plugin", lambda p: False)
        cli._register_commands(test_group)
        # All built-in commands should have been skipped
        assert not test_group.commands


class TestCreateExtractor:
    """Tests for create_extractor helper."""

    def test_create_extractor_success(self) -> None:
        """Test create_extractor succeeds."""
        extractor = create_extractor()
        assert isinstance(extractor, PDFFormService)

    def test_create_extractor_with_geometry(self) -> None:
        """Test create_extractor with geometry option."""
        extractor = create_extractor(extract_geometry=False)
        assert isinstance(extractor, PDFFormService)
        assert extractor._extract_geometry is False
