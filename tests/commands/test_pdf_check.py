"""Tests for the check command."""

from __future__ import annotations

from click.testing import CliRunner

from privacyforms_pdf.cli import main


class TestCheckCommand:
    """Tests for the check command."""

    def test_check_success(self, runner: CliRunner) -> None:
        """Test check command when pypdf is available."""
        result = runner.invoke(main, ["check"])
        assert result.exit_code == 0
        assert "ready" in result.output.lower() or "pypdf" in result.output.lower()
