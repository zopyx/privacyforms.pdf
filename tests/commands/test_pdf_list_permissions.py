"""Tests for the list-permissions command."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from privacyforms_pdf.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


class TestListPermissionsCommand:
    """Tests for the list-permissions command."""

    def test_list_permissions_basic(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test listing permissions of an encrypted PDF."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        mock_output = """permission bits: 111100001100 (xF0C)
Bit  3: true (print(rev2), print quality(rev>=3))
Bit  4: true (modify other than controlled by bits 6,9,11)
Bit  5: true (extract(rev2), extract other than controlled by bit 10(rev>=3))
Bit  6: true (add or modify annotations)
Bit  9: false (fill in form fields(rev>=3)
Bit 10: false (extract(rev>=3))
Bit 11: false (modify(rev>=3))
Bit 12: false (print high-level(rev>=3))"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""
            result = runner.invoke(main, ["list-permissions", str(pdf_file)])
            assert result.exit_code == 0
            assert "PDF Permissions" in result.output
            assert "print" in result.output.lower()

    def test_list_permissions_raw(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test listing permissions with raw output."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        mock_output = "permission bits: 000000000000 (x000)\nBit 3: false"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""
            result = runner.invoke(main, ["list-permissions", str(pdf_file), "--raw"])
            assert result.exit_code == 0
            assert "permission bits:" in result.output.lower()

    def test_list_permissions_with_password(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test listing permissions with user password."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        mock_output = "permission bits: 000000000000 (x000)\nBit 3: false"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""
            result = runner.invoke(main, ["list-permissions", str(pdf_file), "-upw", "userpass"])
            assert result.exit_code == 0

    def test_list_permissions_password_required(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test listing permissions when password is required."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "Please provide the correct password"
            result = runner.invoke(main, ["list-permissions", str(pdf_file)])
            assert result.exit_code != 0
            assert "password" in result.output.lower()

    def test_list_permissions_pdfcpu_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test listing permissions when pdfcpu is not found."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run", side_effect=FileNotFoundError("pdfcpu not found")):
            result = runner.invoke(main, ["list-permissions", str(pdf_file)])
            assert result.exit_code != 0
            assert "pdfcpu not found" in result.output.lower()

    def test_list_permissions_non_encrypted(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test listing permissions of non-encrypted PDF."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(main, ["list-permissions", str(pdf_file)])
            assert result.exit_code == 0
            assert "not encrypted" in result.output.lower()

    def test_list_permissions_with_owner_password(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test listing permissions with owner password."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        mock_output = "permission bits: 111111111111 (xFFF)\nBit 3: true"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""
            result = runner.invoke(main, ["list-permissions", str(pdf_file), "-opw", "ownerpass"])
            assert result.exit_code == 0

    def test_list_permissions_custom_pdfcpu_path(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test listing permissions with custom pdfcpu path."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        mock_output = "permission bits: 000000000000 (x000)\nBit 3: false"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                [
                    "list-permissions",
                    str(pdf_file),
                    "--pdfcpu-path",
                    "/custom/pdfcpu",
                ],
            )
            assert result.exit_code == 0
            # Verify custom path is used
            call_args = mock_run.call_args
            assert "/custom/pdfcpu" in call_args[0][0]

    def test_list_permissions_nonexistent_file(self, runner: CliRunner) -> None:
        """Test listing permissions with nonexistent file."""
        result = runner.invoke(main, ["list-permissions", "/nonexistent/file.pdf"])
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "invalid" in result.output.lower()

    def test_list_permissions_help(self, runner: CliRunner) -> None:
        """Test list-permissions command help."""
        result = runner.invoke(main, ["list-permissions", "--help"])
        assert result.exit_code == 0
        assert "permissions" in result.output.lower()
        assert "user-password" in result.output.lower() or "upw" in result.output.lower()

    def test_list_permissions_pdf_processing_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling of PDF processing errors (e.g., malformed PDF)."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "dict=formFieldDict required entry=DA missing"
            result = runner.invoke(main, ["list-permissions", str(pdf_file)])
            assert result.exit_code != 0
            assert "pdfcpu could not process this pdf" in result.output.lower()
            assert "not encrypted" in result.output.lower() or "malformed" in result.output.lower()
            assert "pdf-forms info" in result.output.lower()


class TestPermissionParser:
    """Tests for the permission parser."""

    def test_parse_permission_bits(self) -> None:
        """Test parsing pdfcpu permission output."""
        from privacyforms_pdf.commands.pdf_list_permissions import parse_permission_bits

        mock_output = """permission bits: 111100001100 (xF0C)
Bit  3: true (print)
Bit  4: false (modify)"""

        result = parse_permission_bits(mock_output)
        assert result["is_encrypted"] is True
        assert result["raw_bits"] == "111100001100"
        assert result["hex_value"] == "F0C"
        assert 3 in result["permissions"]
        assert result["permissions"][3]["value"] is True
        assert result["permissions"][4]["value"] is False

    def test_parse_permission_bits_not_encrypted(self) -> None:
        """Test parsing output for non-encrypted document."""
        from privacyforms_pdf.commands.pdf_list_permissions import parse_permission_bits

        mock_output = ""  # Empty output for non-encrypted

        result = parse_permission_bits(mock_output)
        assert result["is_encrypted"] is False
        assert result["permissions"] == {}


class TestPermissionFormatter:
    """Tests for the permission formatter."""

    def test_format_permissions_highlevel(self) -> None:
        """Test high-level permission formatting."""
        from privacyforms_pdf.commands.pdf_list_permissions import (
            format_permissions_highlevel,
        )

        permissions = {
            "raw_bits": "111100001100",
            "hex_value": "F0C",
            "permissions": {
                3: {"value": True, "description": "print"},
                4: {"value": True, "description": "modify"},
                5: {"value": True, "description": "extract"},
                6: {"value": True, "description": "annotations"},
                9: {"value": False, "description": "fill forms"},
                10: {"value": False, "description": "extract accessibility"},
                11: {"value": False, "description": "assemble"},
                12: {"value": False, "description": "print high"},
            },
            "is_encrypted": True,
        }

        formatted = format_permissions_highlevel(permissions)
        assert "PDF Permissions" in formatted
        assert "Allowed permissions:" in formatted
        assert "Denied permissions:" in formatted
        assert "print" in formatted.lower()

    def test_format_permissions_not_encrypted(self) -> None:
        """Test formatting for non-encrypted document."""
        from privacyforms_pdf.commands.pdf_list_permissions import (
            format_permissions_highlevel,
        )

        permissions = {
            "raw_bits": "",
            "hex_value": "",
            "permissions": {},
            "is_encrypted": False,
        }

        formatted = format_permissions_highlevel(permissions)
        assert "not encrypted" in formatted.lower()
        assert "all permissions granted" in formatted.lower()
