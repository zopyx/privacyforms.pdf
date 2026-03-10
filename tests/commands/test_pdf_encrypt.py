"""Tests for the encrypt command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from privacyforms_pdf.cli import main


class TestEncryptCommand:
    """Tests for the encrypt command."""

    def test_encrypt_basic(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test basic encryption with owner password."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = runner.invoke(main, ["encrypt", str(pdf_file), "-opw", "ownerpass"])
            assert result.exit_code == 0
            assert "encrypted" in result.output.lower()

    def test_encrypt_with_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption with output file."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")
        output_file = tmp_path / "encrypted.pdf"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main, ["encrypt", str(pdf_file), str(output_file), "-opw", "ownerpass"]
            )
            assert result.exit_code == 0
            assert "encrypted and saved to" in result.output.lower()

    def test_encrypt_with_user_password(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption with both owner and user passwords."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                ["encrypt", str(pdf_file), "-opw", "ownerpass", "-upw", "userpass"],
            )
            assert result.exit_code == 0
            assert "encrypted" in result.output.lower()

    def test_encrypt_with_options(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption with all options specified."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                [
                    "encrypt",
                    str(pdf_file),
                    "-opw",
                    "ownerpass",
                    "-upw",
                    "userpass",
                    "--mode",
                    "aes",
                    "--key",
                    "256",
                    "--perm",
                    "none",
                ],
            )
            assert result.exit_code == 0
            assert "encrypted" in result.output.lower()

    def test_encrypt_missing_owner_password(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption fails without owner password."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        result = runner.invoke(main, ["encrypt", str(pdf_file)])
        assert result.exit_code != 0
        assert "missing option" in result.output.lower() or "required" in result.output.lower()

    def test_encrypt_pdfcpu_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption handles pdfcpu not found error."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run", side_effect=FileNotFoundError("pdfcpu not found")):
            result = runner.invoke(main, ["encrypt", str(pdf_file), "-opw", "ownerpass"])
            assert result.exit_code != 0
            assert "pdfcpu not found" in result.output.lower()

    def test_encrypt_pdfcpu_command_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption handles pdfcpu command not found in stderr."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        from subprocess import CalledProcessError

        with patch(
            "subprocess.run",
            side_effect=CalledProcessError(1, ["pdfcpu"], stderr="command not found"),
        ):
            result = runner.invoke(main, ["encrypt", str(pdf_file), "-opw", "ownerpass"])
            assert result.exit_code != 0
            assert "pdfcpu not found" in result.output.lower()

    def test_encrypt_pdfcpu_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption handles generic pdfcpu error."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        from subprocess import CalledProcessError

        with patch(
            "subprocess.run",
            side_effect=CalledProcessError(1, ["pdfcpu"], stderr="Invalid PDF"),
        ):
            result = runner.invoke(main, ["encrypt", str(pdf_file), "-opw", "ownerpass"])
            assert result.exit_code != 0
            assert "encryption failed" in result.output.lower()

    def test_encrypt_with_custom_pdfcpu_path(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption with custom pdfcpu path."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                [
                    "encrypt",
                    str(pdf_file),
                    "-opw",
                    "ownerpass",
                    "--pdfcpu-path",
                    "/custom/path/to/pdfcpu",
                ],
            )
            assert result.exit_code == 0
            mock_run.assert_called_once()
            # Verify the custom path is used
            call_args = mock_run.call_args
            assert "/custom/path/to/pdfcpu" in call_args[0][0]

    def test_encrypt_rc4_mode(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption with RC4 mode."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main, ["encrypt", str(pdf_file), "-opw", "ownerpass", "--mode", "rc4"]
            )
            assert result.exit_code == 0
            # Check that rc4 mode is passed to subprocess
            call_args = mock_run.call_args
            assert "-mode" in call_args[0][0]
            assert "rc4" in call_args[0][0]

    def test_encrypt_all_permissions(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test encryption with all permissions."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = runner.invoke(
                main,
                ["encrypt", str(pdf_file), "-opw", "ownerpass", "--perm", "all"],
            )
            assert result.exit_code == 0
            # Check that all perm is passed to subprocess
            call_args = mock_run.call_args
            assert "-perm" in call_args[0][0]
            assert "all" in call_args[0][0]

    def test_encrypt_nonexistent_file(self, runner: CliRunner) -> None:
        """Test encryption with nonexistent file."""
        result = runner.invoke(main, ["encrypt", "/nonexistent/file.pdf", "-opw", "pass"])
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "invalid" in result.output.lower()

    def test_encrypt_help(self, runner: CliRunner) -> None:
        """Test encrypt command help."""
        result = runner.invoke(main, ["encrypt", "--help"])
        assert result.exit_code == 0
        assert "owner-password" in result.output.lower() or "opw" in result.output.lower()
        assert "user-password" in result.output.lower() or "upw" in result.output.lower()
        assert "mode" in result.output.lower()
        assert "encrypt" in result.output.lower()
