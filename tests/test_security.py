"""Tests for PDFSecurityManager and security utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from privacyforms_pdf.models import PDFFormError
from privacyforms_pdf.security import (
    PDFSecurityManager,
    build_permission_bits,
    format_permissions_highlevel,
    parse_permission_bits,
)


class TestBuildPermissionBits:
    """Tests for build_permission_bits."""

    def test_all_false(self) -> None:
        """Test all permissions false."""
        result = build_permission_bits()
        assert result == "000000000000"

    def test_all_true(self) -> None:
        """Test all permissions true."""
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
        assert result == "001111001111"

    def test_print_only(self) -> None:
        """Test print permission only."""
        result = build_permission_bits(print_perm=True)
        assert result[2] == "1"
        assert result.count("1") == 1


class TestParsePermissionBits:
    """Tests for parse_permission_bits."""

    def test_encrypted_document(self) -> None:
        """Test parsing encrypted document output."""
        output = "permission bits: 111100111100 (xF3C)\nbit 3: true (Print)\nbit 4: false (Modify)"
        result = parse_permission_bits(output)
        assert result["is_encrypted"] is True
        assert result["raw_bits"] == "111100111100"
        assert result["hex_value"] == "F3C"
        assert 3 in result["permissions"]

    def test_not_encrypted(self) -> None:
        """Test parsing non-encrypted document output."""
        result = parse_permission_bits("No permission bits found")
        assert result["is_encrypted"] is False
        assert result["raw_bits"] == ""


class TestFormatPermissionsHighlevel:
    """Tests for format_permissions_highlevel."""

    def test_not_encrypted(self) -> None:
        """Test formatting for non-encrypted document."""
        permissions = {
            "raw_bits": "",
            "hex_value": "",
            "permissions": {},
            "is_encrypted": False,
        }
        result = format_permissions_highlevel(permissions)
        assert "not encrypted" in result.lower()

    def test_encrypted_with_mixed_permissions(self) -> None:
        """Test formatting for encrypted document with mixed permissions."""
        permissions = {
            "raw_bits": "001000000000",
            "hex_value": "200",
            "permissions": {
                3: {"value": True, "description": "Print"},
                4: {"value": False, "description": "Modify"},
            },
            "is_encrypted": True,
        }
        result = format_permissions_highlevel(permissions)
        assert "Raw permission bits" in result
        assert "print" in result.lower()


class TestPDFSecurityManager:
    """Tests for PDFSecurityManager."""

    def test_init_defaults(self) -> None:
        """Test initialization with defaults."""
        manager = PDFSecurityManager()
        assert manager._pdfcpu_path == "pdfcpu"
        assert manager._timeout_seconds == 30.0

    def test_resolve_pdfcpu_not_found(self) -> None:
        """Test resolving pdfcpu when not found."""
        manager = PDFSecurityManager(pdfcpu_path="/nonexistent/pdfcpu")
        with pytest.raises(PDFFormError, match="pdfcpu binary not found"):
            manager._resolve_pdfcpu()

    def test_encrypt_success(self, tmp_path: Path) -> None:
        """Test encrypt succeeds."""
        manager = PDFSecurityManager()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        output_file = tmp_path / "encrypted.pdf"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = ""

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(manager, "_run", return_value=mock_result),
        ):
            result = manager.encrypt(
                pdf_file,
                output_file,
                owner_password="ownerpass",
            )
            assert result == output_file

    def test_encrypt_failure(self, tmp_path: Path) -> None:
        """Test encrypt raises on failure."""
        manager = PDFSecurityManager()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "encryption failed"
        mock_result.stdout = ""

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(manager, "_run", return_value=mock_result),
            pytest.raises(PDFFormError, match="encryption failed"),
        ):
            manager.encrypt(pdf_file, owner_password="ownerpass")

    def test_set_permissions_success(self, tmp_path: Path) -> None:
        """Test set_permissions succeeds."""
        manager = PDFSecurityManager()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = "Permissions updated"

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(manager, "_run", return_value=mock_result),
        ):
            manager.set_permissions(pdf_file, owner_password="ownerpass", permissions_preset="none")

    def test_set_permissions_wrong_password(self, tmp_path: Path) -> None:
        """Test set_permissions raises on wrong password."""
        manager = PDFSecurityManager()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = "please provide the owner password"
        mock_result.stdout = ""

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(manager, "_run", return_value=mock_result),
            pytest.raises(PDFFormError, match="Incorrect owner password"),
        ):
            manager.set_permissions(pdf_file, owner_password="wrongpass")

    def test_set_permissions_not_encrypted(self, tmp_path: Path) -> None:
        """Test set_permissions raises when document not encrypted."""
        manager = PDFSecurityManager()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = "not encrypted"

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(manager, "_run", return_value=mock_result),
            pytest.raises(PDFFormError, match="not encrypted"),
        ):
            manager.set_permissions(pdf_file, owner_password="ownerpass")

    def test_set_permissions_pdfcpu_error(self, tmp_path: Path) -> None:
        """Test set_permissions raises on pdfcpu error."""
        manager = PDFSecurityManager()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "some error"
        mock_result.stdout = ""

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(manager, "_run", return_value=mock_result),
            pytest.raises(PDFFormError, match="some error"),
        ):
            manager.set_permissions(pdf_file, owner_password="ownerpass")

    def test_list_permissions_success(self, tmp_path: Path) -> None:
        """Test list_permissions succeeds."""
        manager = PDFSecurityManager()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = "permission bits: 111100111100 (xF3C)\nbit 3: true (Print)"

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(manager, "_run", return_value=mock_result),
        ):
            result = manager.list_permissions(pdf_file)
            assert result["is_encrypted"] is True
            assert result["raw_bits"] == "111100111100"

    def test_list_permissions_password_required(self, tmp_path: Path) -> None:
        """Test list_permissions raises when password required."""
        manager = PDFSecurityManager()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = "please provide the correct password"
        mock_result.stdout = ""

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(manager, "_run", return_value=mock_result),
            pytest.raises(PDFFormError, match="requires a password"),
        ):
            manager.list_permissions(pdf_file)

    def test_list_permissions_pdfcpu_failure(self, tmp_path: Path) -> None:
        """Test list_permissions raises on pdfcpu failure."""
        manager = PDFSecurityManager()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "failed to list"
        mock_result.stdout = ""

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/usr/bin/pdfcpu"),
            patch.object(manager, "_run", return_value=mock_result),
            pytest.raises(PDFFormError, match="failed to list"),
        ):
            manager.list_permissions(pdf_file)

    def test_run_file_not_found(self) -> None:
        """Test _run handles FileNotFoundError."""
        manager = PDFSecurityManager(pdfcpu_path="/nonexistent")

        with (
            patch.object(manager, "_resolve_pdfcpu", return_value="/nonexistent/pdfcpu"),
            patch("privacyforms_pdf.security.subprocess.run", side_effect=FileNotFoundError()),
            pytest.raises(PDFFormError, match="pdfcpu binary not found"),
        ):
            manager._run(["/nonexistent/pdfcpu", "encrypt", "test.pdf"])


class TestPDFFormExtractorSecurityMethods:
    """Tests for security methods exposed via PDFFormExtractor."""

    def test_extractor_encrypt_delegates(self, tmp_path: Path) -> None:
        """Test PDFFormExtractor.encrypt delegates to PDFSecurityManager."""
        from privacyforms_pdf.extractor import PDFFormExtractor

        extractor = PDFFormExtractor()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        output_file = tmp_path / "encrypted.pdf"

        with patch.object(extractor._security, "encrypt", return_value=output_file) as mock_encrypt:
            result = extractor.encrypt(
                pdf_file,
                output_file,
                owner_password="ownerpass",
                user_password="userpass",
            )
            assert result == output_file
            mock_encrypt.assert_called_once_with(
                pdf_file,
                output_file,
                owner_password="ownerpass",
                user_password="userpass",
                mode="aes",
                key_length="256",
                permissions="none",
            )

    def test_extractor_set_permissions_delegates(self, tmp_path: Path) -> None:
        """Test PDFFormExtractor.set_permissions delegates to PDFSecurityManager."""
        from privacyforms_pdf.extractor import PDFFormExtractor

        extractor = PDFFormExtractor()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        with patch.object(extractor._security, "set_permissions") as mock_set:
            extractor.set_permissions(
                pdf_file,
                owner_password="ownerpass",
                permissions_preset="print",
            )
            mock_set.assert_called_once_with(
                pdf_file,
                owner_password="ownerpass",
                user_password=None,
                permissions_preset="print",
                print_perm=False,
                modify=False,
                extract=False,
                annotations=False,
                fill_forms=False,
                extract_accessibility=False,
                assemble=False,
                print_high=False,
                custom_bits=None,
            )

    def test_extractor_list_permissions_delegates(self, tmp_path: Path) -> None:
        """Test PDFFormExtractor.list_permissions delegates to PDFSecurityManager."""
        from privacyforms_pdf.extractor import PDFFormExtractor

        extractor = PDFFormExtractor()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        expected = {"is_encrypted": True, "raw_bits": "1111", "hex_value": "F", "permissions": {}}

        with patch.object(
            extractor._security, "list_permissions", return_value=expected
        ) as mock_list:
            result = extractor.list_permissions(pdf_file, user_password="userpass")
            assert result == expected
            mock_list.assert_called_once_with(
                pdf_file,
                user_password="userpass",
                owner_password=None,
            )
