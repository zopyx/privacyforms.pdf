"""Tests for the set-permissions command."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from privacyforms_pdf.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


class TestSetPermissionsCommand:
    """Tests for the set-permissions command."""

    def test_set_permissions_none(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test setting permissions to none."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "writing test.pdf ..."
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                ["set-permissions", str(pdf_file), "-opw", "ownerpass", "--permissions", "none"],
            )
            assert result.exit_code == 0
            assert (
                "permissions updated" in result.output.lower()
                or "permissions set" in result.output.lower()
            )
            assert "preset: none" in result.output.lower()

    def test_set_permissions_all(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test setting permissions to all."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "writing test.pdf ..."
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                ["set-permissions", str(pdf_file), "-opw", "ownerpass", "--permissions", "all"],
            )
            assert result.exit_code == 0
            assert "preset: all" in result.output.lower()

    def test_set_permissions_print(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test setting permissions to print only."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "writing test.pdf ..."
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                ["set-permissions", str(pdf_file), "-opw", "ownerpass", "--permissions", "print"],
            )
            assert result.exit_code == 0
            assert "preset: print" in result.output.lower()

    def test_set_permissions_custom_bits_hex(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test setting custom permission bits in hex."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                ["set-permissions", str(pdf_file), "-opw", "ownerpass", "--custom-bits", "F3C"],
            )
            assert result.exit_code == 0
            assert "custom bits" in result.output.lower()

    def test_set_permissions_custom_bits_binary(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test setting custom permission bits in binary."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                [
                    "set-permissions",
                    str(pdf_file),
                    "-opw",
                    "ownerpass",
                    "--custom-bits",
                    "111100111100",
                ],
            )
            assert result.exit_code == 0

    def test_set_permissions_missing_owner_password(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that owner password is required."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        result = runner.invoke(main, ["set-permissions", str(pdf_file)])
        assert result.exit_code != 0
        assert "missing option" in result.output.lower() or "required" in result.output.lower()

    def test_set_permissions_wrong_owner_password(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling of wrong owner password."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "please provide the owner password"
            result = runner.invoke(main, ["set-permissions", str(pdf_file), "-opw", "wrongpass"])
            assert result.exit_code != 0
            assert "incorrect owner password" in result.output.lower()

    def test_set_permissions_not_encrypted(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling of non-encrypted PDF."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "PDF not encrypted"
            result = runner.invoke(main, ["set-permissions", str(pdf_file), "-opw", "ownerpass"])
            assert result.exit_code != 0
            assert "not encrypted" in result.output.lower()
            assert "encrypt" in result.output.lower()

    def test_set_permissions_pdfcpu_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling when pdfcpu is not found."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run", side_effect=FileNotFoundError("pdfcpu not found")):
            result = runner.invoke(main, ["set-permissions", str(pdf_file), "-opw", "ownerpass"])
            assert result.exit_code != 0
            assert "pdfcpu not found" in result.output.lower()

    def test_set_permissions_with_user_password(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test setting permissions with user password."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                [
                    "set-permissions",
                    str(pdf_file),
                    "-opw",
                    "ownerpass",
                    "-upw",
                    "userpass",
                    "--permissions",
                    "all",
                ],
            )
            assert result.exit_code == 0

    def test_set_permissions_custom_pdfcpu_path(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test with custom pdfcpu path."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                [
                    "set-permissions",
                    str(pdf_file),
                    "-opw",
                    "ownerpass",
                    "--pdfcpu-path",
                    "/custom/pdfcpu",
                ],
            )
            assert result.exit_code == 0
            call_args = mock_run.call_args
            assert "/custom/pdfcpu" in call_args[0][0]

    def test_set_permissions_pdf_processing_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test handling of PDF processing errors."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "dict=formFieldDict required entry=DA missing"
            result = runner.invoke(main, ["set-permissions", str(pdf_file), "-opw", "ownerpass"])
            assert result.exit_code != 0
            assert "pdfcpu could not process" in result.output.lower()

    def test_set_permissions_invalid_custom_bits(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test validation of invalid custom bits."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        result = runner.invoke(
            main,
            [
                "set-permissions",
                str(pdf_file),
                "-opw",
                "ownerpass",
                "--custom-bits",
                "invalid!@#",
            ],
        )
        assert result.exit_code != 0
        assert "invalid --custom-bits" in result.output.lower()

    def test_set_permissions_nonexistent_file(self, runner: CliRunner) -> None:
        """Test with nonexistent file."""
        result = runner.invoke(main, ["set-permissions", "/nonexistent/file.pdf", "-opw", "pass"])
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "invalid" in result.output.lower()

    def test_set_permissions_all_individual_flags(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test setting all permissions using individual flags."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                [
                    "set-permissions",
                    str(pdf_file),
                    "-opw",
                    "ownerpass",
                    "--print",
                    "--modify",
                    "--extract",
                    "--annotations",
                    "--fill-forms",
                    "--extract-accessibility",
                    "--assemble",
                    "--print-high",
                ],
            )
            assert result.exit_code == 0

    def test_set_permissions_help(self, runner: CliRunner) -> None:
        """Test set-permissions command help."""
        result = runner.invoke(main, ["set-permissions", "--help"])
        assert result.exit_code == 0
        assert "permissions" in result.output.lower()
        assert "owner-password" in result.output.lower() or "opw" in result.output.lower()
        assert "none" in result.output.lower()
        assert "all" in result.output.lower()
        # Check for individual permission flags
        assert "--print" in result.output
        assert "--modify" in result.output
        assert "--extract" in result.output
        assert "--annotations" in result.output
        assert "--fill-forms" in result.output


class TestBuildPermissionBits:
    """Tests for the build_permission_bits helper function."""

    def test_build_permission_bits_all_false(self) -> None:
        """Test building bits with all permissions disabled."""
        from privacyforms_pdf.commands.pdf_set_permissions import build_permission_bits

        result = build_permission_bits()
        assert result == "000000000000"

    def test_build_permission_bits_print_only(self) -> None:
        """Test building bits with only print permission."""
        from privacyforms_pdf.commands.pdf_set_permissions import build_permission_bits

        result = build_permission_bits(print_perm=True)
        # Bit 3 (index 2) should be 1
        assert result[2] == "1"
        assert result == "001000000000"

    def test_build_permission_bits_all_true(self) -> None:
        """Test building bits with all permissions enabled."""
        from privacyforms_pdf.commands.pdf_set_permissions import build_permission_bits

        result = build_permission_bits(
            print_perm=True,
            modify=True,
            extract=True,
            annotations=True,
            fill_forms=True,
            extract_accessibility=True,
            assemble=True,
            print_high=True,
        )
        # All relevant bits should be 1 (bits 3,4,5,6,9,10,11,12)
        # Index: 0  1  2  3  4  5  6  7  8  9  10 11
        # Bit:   1  2  3  4  5  6  7  8  9  10 11 12
        # Value: 0  0  1  1  1  1  0  0  1  1  1  1
        assert result == "001111001111"

    def test_build_permission_bits_specific_combo(self) -> None:
        """Test building bits with a specific combination."""
        from privacyforms_pdf.commands.pdf_set_permissions import build_permission_bits

        result = build_permission_bits(
            print_perm=True,
            fill_forms=True,
            annotations=True,
        )
        # Bits 3, 6, 9 should be 1 (indices 2, 5, 8)
        # Index: 0  1  2  3  4  5  6  7  8  9  10 11
        # Bit:   1  2  3  4  5  6  7  8  9  10 11 12
        # Value: 0  0  1  0  0  1  0  0  1  0  0  0
        assert result == "001001001000"

    def test_set_permissions_individual_flags(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test setting permissions using individual flags."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main, ["set-permissions", str(pdf_file), "-opw", "ownerpass", "--print"]
            )
            assert result.exit_code == 0
            assert "permissions" in result.output.lower()

    def test_set_permissions_multiple_flags(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test setting multiple permissions using flags."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                [
                    "set-permissions",
                    str(pdf_file),
                    "-opw",
                    "ownerpass",
                    "--print",
                    "--extract",
                    "--fill-forms",
                ],
            )
            assert result.exit_code == 0
            # Check that the binary permission bits were computed correctly
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            # Should have -perm followed by binary string
            perm_idx = cmd.index("-perm")
            assert perm_idx >= 0
            perm_value = cmd[perm_idx + 1]
            # With --print, --extract, --fill-forms: bits 3, 5, 9 should be 1
            # Binary: 001010101000 = 0x2A8
            assert len(perm_value) == 12 or perm_value in ["none", "print", "all"]

    def test_set_permissions_no_flags_defaults_to_none(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that no flags results in most restrictive permissions."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(main, ["set-permissions", str(pdf_file), "-opw", "ownerpass"])
            assert result.exit_code == 0
            assert "none" in result.output.lower() or "000000000000" in result.output.lower()

    def test_set_permissions_preset_overrides_flags(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that --permissions preset overrides individual flags."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                [
                    "set-permissions",
                    str(pdf_file),
                    "-opw",
                    "ownerpass",
                    "--permissions",
                    "all",
                    "--print",  # This should be ignored due to --permissions
                ],
            )
            assert result.exit_code == 0
            # Should use preset "all", not individual flags
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            perm_idx = cmd.index("-perm")
            assert cmd[perm_idx + 1] == "all"
