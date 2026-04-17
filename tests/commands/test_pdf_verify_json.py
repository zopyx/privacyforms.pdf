"""Tests for pdf-forms verify-json command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner

from privacyforms_pdf.cli import main

if TYPE_CHECKING:
    from pathlib import Path


class TestVerifyJsonCommand:
    """Tests for verify-json command."""

    def test_verify_json_success(self, tmp_path: Path) -> None:
        """Test verify-json with valid schema."""
        runner = CliRunner()
        json_file = tmp_path / "form.json"
        json_file.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )

        result = runner.invoke(main, ["verify-json", str(json_file)])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_verify_json_invalid(self, tmp_path: Path) -> None:
        """Test verify-json with invalid schema."""
        runner = CliRunner()
        json_file = tmp_path / "form.json"
        json_file.write_text('{"spec_version": "1.0", "fields": "bad"}')

        result = runner.invoke(main, ["verify-json", str(json_file)])
        assert result.exit_code != 0
        assert "Invalid" in result.output
