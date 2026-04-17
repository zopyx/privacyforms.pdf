"""Tests for pdf-forms verify-data command."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from privacyforms_pdf.cli import main
from privacyforms_pdf.commands.pdf_verify_data import _check_json_size
from privacyforms_pdf.json_utils import (
    check_json_depth,
    require_json_object,
    safe_json_loads,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestVerifyDataCommand:
    """Tests for verify-data command."""

    def test_verify_data_success(self, tmp_path: Path) -> None:
        """Test verify-data with matching keys."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"f-0": "John"}')

        result = runner.invoke(
            main,
            ["verify-data", "--form-json", str(form_json), "--data-json", str(data_json)],
        )
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_verify_data_missing_key(self, tmp_path: Path) -> None:
        """Test verify-data fails when data key is missing from form."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"f-1": "John"}')

        result = runner.invoke(
            main,
            ["verify-data", "--form-json", str(form_json), "--data-json", str(data_json)],
        )
        assert result.exit_code != 0
        assert "f-1" in result.output
        assert "not found" in result.output

    def test_verify_data_with_list_value(self, tmp_path: Path) -> None:
        """Test verify-data when data JSON contains a list value."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"f-0": ["a", "b"]}')

        result = runner.invoke(
            main,
            ["verify-data", "--form-json", str(form_json), "--data-json", str(data_json)],
        )
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_verify_data_success_with_name_keys(self, tmp_path: Path) -> None:
        """Test verify-data with matching field-name keys."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "Candidate Name", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"Candidate Name": "John"}')

        result = runner.invoke(
            main,
            [
                "verify-data",
                "--form-json",
                str(form_json),
                "--data-json",
                str(data_json),
                "--key-mode",
                "name",
            ],
        )
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_verify_data_success_with_auto_keys(self, tmp_path: Path) -> None:
        """Test verify-data with mixed field-name and field-ID keys."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "Candidate Name", "id": "f-0", "type": "textfield"}, '
            '{"name": "Agree", "id": "f-1", "type": "checkbox"}], "rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"Candidate Name": "John", "f-1": true}')

        result = runner.invoke(
            main,
            ["verify-data", "--form-json", str(form_json), "--data-json", str(data_json)],
        )
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_verify_data_json_too_large(self, tmp_path: Path) -> None:
        """Test verify-data fails when a JSON file exceeds the size limit."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"f-0": "John"}')

        with patch(
            "privacyforms_pdf.commands.pdf_verify_data._check_json_size",
            side_effect=click.ClickException("too large"),
        ):
            result = runner.invoke(
                main,
                [
                    "verify-data",
                    "--form-json",
                    str(form_json),
                    "--data-json",
                    str(data_json),
                ],
            )
        assert result.exit_code != 0
        assert "too large" in result.output

    def test_verify_data_json_not_object(self, tmp_path: Path) -> None:
        """Test verify-data fails when data JSON is not a top-level object."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('["not", "an", "object"]')

        result = runner.invoke(
            main,
            ["verify-data", "--form-json", str(form_json), "--data-json", str(data_json)],
        )
        assert result.exit_code != 0
        assert "must be a top-level object" in result.output

    def test_verify_data_id_mode_success(self, tmp_path: Path) -> None:
        """Test verify-data with matching field IDs in id mode."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"f-0": "John"}')

        result = runner.invoke(
            main,
            [
                "verify-data",
                "--form-json",
                str(form_json),
                "--data-json",
                str(data_json),
                "--key-mode",
                "id",
            ],
        )
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_verify_data_id_mode_reports_id_lookup(self, tmp_path: Path) -> None:
        """Test verify-data id mode reports missing field IDs."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"f-1": "John"}')

        result = runner.invoke(
            main,
            [
                "verify-data",
                "--form-json",
                str(form_json),
                "--data-json",
                str(data_json),
                "--key-mode",
                "id",
            ],
        )
        assert result.exit_code != 0
        assert "field IDs" in result.output

    def test_verify_data_name_mode_reports_name_lookup(self, tmp_path: Path) -> None:
        """Test verify-data name mode reports missing field names."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "Candidate Name", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"f-0": "John"}')

        result = runner.invoke(
            main,
            [
                "verify-data",
                "--form-json",
                str(form_json),
                "--data-json",
                str(data_json),
                "--key-mode",
                "name",
            ],
        )
        assert result.exit_code != 0
        assert "field names" in result.output

    def test_verify_data_json_too_deep(self, tmp_path: Path) -> None:
        """Test verify-data fails when JSON nesting exceeds the depth limit."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        deep = {"key": "value"}
        for _ in range(55):
            deep = {"nested": deep}
        import json

        data_json.write_text(json.dumps(deep))

        result = runner.invoke(
            main,
            ["verify-data", "--form-json", str(form_json), "--data-json", str(data_json)],
        )
        assert result.exit_code != 0
        assert "maximum nesting depth" in result.output

    def test_verify_data_json_recursion_error(self, tmp_path: Path) -> None:
        """Test verify-data fails gracefully when json.loads raises RecursionError."""
        runner = CliRunner()
        form_json = tmp_path / "form.json"
        form_json.write_text(
            '{"spec_version": "1.0", "source": "test.pdf", '
            '"fields": [{"name": "f1", "id": "f-0", "type": "textfield"}], '
            '"rows": []}'
        )
        data_json = tmp_path / "data.json"
        data_json.write_text('{"f-0": "John"}')

        with patch(
            "privacyforms_pdf.json_utils.json.loads",
            side_effect=RecursionError("deep"),
        ):
            result = runner.invoke(
                main,
                [
                    "verify-data",
                    "--form-json",
                    str(form_json),
                    "--data-json",
                    str(data_json),
                ],
            )
        assert result.exit_code != 0
        assert "too deeply nested" in result.output


class TestHelperFunctions:
    """Direct tests for shared JSON helper functions."""

    def test_check_json_size_exceeds_limit(self, tmp_path: Path) -> None:
        """Test _check_json_size raises ClickException for oversized files."""
        path = tmp_path / "big.json"
        path.write_text("x")
        with pytest.raises(click.ClickException, match="too large"):
            _check_json_size(path, max_size=0)

    def test_check_json_depth_list(self) -> None:
        """Test check_json_depth iterates over list items."""
        obj = [{"nested": [1, 2, 3]}, "string"]
        check_json_depth(obj)

    def test_check_json_depth_exceeds_max(self) -> None:
        """Test check_json_depth raises ValueError when depth exceeds max."""
        deep = {"key": "value"}
        for _ in range(55):
            deep = {"nested": deep}
        with pytest.raises(ValueError, match="exceeds maximum nesting depth"):
            check_json_depth(deep)

    def test_safe_json_loads_recursion_error(self) -> None:
        """Test safe_json_loads raises ValueError on RecursionError."""
        with (
            patch(
                "privacyforms_pdf.json_utils.json.loads",
                side_effect=RecursionError("deep"),
            ),
            pytest.raises(ValueError, match="too deeply nested"),
        ):
            safe_json_loads("{}")

    def test_require_json_object_not_mapping(self) -> None:
        """Test require_json_object raises ValueError for non-mapping data."""
        with pytest.raises(ValueError, match="top-level object"):
            require_json_object(["not", "an", "object"])
