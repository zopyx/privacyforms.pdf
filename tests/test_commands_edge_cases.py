"""Edge-case tests for CLI commands to boost coverage."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from privacyforms_pdf.cli import main
from privacyforms_pdf.json_utils import check_json_depth, require_json_object, safe_json_loads

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PDF = REPO_ROOT / "samples" / "FilledForm.pdf"


class TestParseCommandEdgeCases:
    """Tests for parse command edge cases."""

    def test_parse_refuses_symlink(self, tmp_path: Path) -> None:
        """It refuses to write output to a symlink."""
        runner = CliRunner()
        pdf = SAMPLE_PDF
        symlink = tmp_path / "link.json"
        symlink.symlink_to(tmp_path / "target.json")
        result = runner.invoke(main, ["parse", str(pdf), str(symlink)])
        assert result.exit_code != 0
        assert "symlink" in result.output.lower() or "Refusing" in result.output

    def test_parse_value_error(self, tmp_path: Path) -> None:
        """It surfaces ValueError from the parser as a ClickException."""
        runner = CliRunner()
        pdf = tmp_path / "form.pdf"
        pdf.write_text("not a pdf")
        with patch("privacyforms_pdf.commands.pdf_parse.extract_pdf_form") as mock_extract:
            mock_extract.side_effect = ValueError("bad pdf")
            result = runner.invoke(main, ["parse", str(pdf)])
        assert result.exit_code != 0
        assert "bad pdf" in result.output


class TestVerifyDataEdgeCases:
    """Tests for verify-data command edge cases."""

    def test_check_json_size_too_large(self, tmp_path: Path) -> None:
        """It raises ClickException when the JSON file is too large."""
        from privacyforms_pdf.commands.pdf_verify_data import _check_json_size

        path = tmp_path / "big.json"
        path.write_text("x")
        os.truncate(path, 11 * 1024 * 1024)
        with pytest.raises(click.ClickException, match="too large"):
            _check_json_size(path)

    def test_check_json_depth_exceeded(self) -> None:
        """It raises ValueError when JSON nesting exceeds the limit."""
        nested = {"a": {"b": {"c": {}}}}
        with pytest.raises(ValueError, match="depth"):
            check_json_depth(nested, depth=0, max_depth=2)

    def test_safe_json_loads_recursion_error(self) -> None:
        """It raises ValueError on RecursionError from json.loads."""
        with (
            patch("privacyforms_pdf.json_utils.json.loads", side_effect=RecursionError("too deep")),
            pytest.raises(ValueError, match="deeply nested"),
        ):
            safe_json_loads("{}")

    def test_require_json_object_not_mapping(self) -> None:
        """It raises ValueError when the top-level JSON is not an object."""
        with pytest.raises(ValueError, match="top-level object"):
            require_json_object([1, 2, 3])


class TestVerifyJsonEdgeCases:
    """Tests for verify-json command edge cases."""

    def test_check_json_size_too_large(self, tmp_path: Path) -> None:
        """It raises ClickException when the JSON file is too large."""
        from privacyforms_pdf.commands.pdf_verify_json import _check_json_size

        path = tmp_path / "big.json"
        path.write_text("x")
        os.truncate(path, 11 * 1024 * 1024)
        with pytest.raises(click.ClickException, match="too large"):
            _check_json_size(path)

    def test_verify_json_invalid_schema(self, tmp_path: Path) -> None:
        """It reports failure for JSON that does not match the schema."""
        runner = CliRunner()
        json_path = tmp_path / "bad.json"
        json_path.write_text('{"fields": [{"name": "A"}]}')
        result = runner.invoke(main, ["verify-json", str(json_path)])
        assert result.exit_code != 0
        assert "Invalid" in result.output or "failed" in result.output.lower()
