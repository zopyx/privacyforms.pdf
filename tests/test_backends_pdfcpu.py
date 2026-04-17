"""Tests for the PdfcpuBackend class."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from privacyforms_pdf.backends.pdfcpu import PdfcpuBackend, is_pdfcpu_available
from privacyforms_pdf.models import PDFFormError

if TYPE_CHECKING:
    from pathlib import Path as PathType


class TestPdfcpuBackendRunCommand:
    """Tests for PdfcpuBackend._run_command."""

    def test_run_command_success(self) -> None:
        """Test _run_command succeeds when subprocess returns 0."""
        backend = PdfcpuBackend()
        with patch("privacyforms_pdf.backends.pdfcpu.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            backend._run_command(["pdfcpu", "version"])
            mock_run.assert_called_once()

    def test_run_command_called_process_error_with_stderr(self) -> None:
        """Test _run_command raises PDFFormError with stderr."""
        backend = PdfcpuBackend()
        with (
            patch(
                "privacyforms_pdf.backends.pdfcpu.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, ["pdfcpu"], stderr="bad args"),
            ),
            pytest.raises(PDFFormError, match="pdfcpu failed with exit code 1: bad args"),
        ):
            backend._run_command(["pdfcpu", "form", "fill"])

    def test_run_command_called_process_error_without_stderr(self) -> None:
        """Test _run_command raises PDFFormError without stderr."""
        backend = PdfcpuBackend()
        with (
            patch(
                "privacyforms_pdf.backends.pdfcpu.subprocess.run",
                side_effect=subprocess.CalledProcessError(2, ["pdfcpu"], stderr=None),
            ),
            pytest.raises(PDFFormError, match="pdfcpu failed with exit code 2$"),
        ):
            backend._run_command(["pdfcpu"])

    def test_run_command_timeout(self) -> None:
        """Test _run_command raises PDFFormError on timeout."""
        backend = PdfcpuBackend(timeout_seconds=5.0)
        with (
            patch(
                "privacyforms_pdf.backends.pdfcpu.subprocess.run",
                side_effect=subprocess.TimeoutExpired("pdfcpu", 5.0),
            ),
            pytest.raises(PDFFormError, match="pdfcpu timed out after 5.0 seconds"),
        ):
            backend._run_command(["pdfcpu"])

    def test_run_command_file_not_found(self) -> None:
        """Test _run_command raises PDFFormError when binary is missing."""
        backend = PdfcpuBackend()
        with (
            patch(
                "privacyforms_pdf.backends.pdfcpu.subprocess.run",
                side_effect=FileNotFoundError("pdfcpu not found"),
            ),
            pytest.raises(PDFFormError, match="pdfcpu binary not found: /custom/pdfcpu"),
        ):
            backend._run_command(["/custom/pdfcpu"])


class TestPdfcpuBackendExportFormData:
    """Tests for PdfcpuBackend._export_form_data."""

    def test_export_form_data_success(self, tmp_path: PathType) -> None:
        """Test exporting form data via pdfcpu."""
        backend = PdfcpuBackend()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake pdf")

        expected_data = {"forms": [{"textfield": [{"id": "1", "name": "Name", "value": ""}]}]}

        with (
            patch.object(backend, "_run_command") as mock_run,
            patch("privacyforms_pdf.backends.pdfcpu.json.load", return_value=expected_data),
        ):
            result = backend._export_form_data(pdf_file, "/usr/bin/pdfcpu")
            assert result == expected_data
            mock_run.assert_called_once()


class TestPdfcpuBackendBuildFieldIndex:
    """Tests for PdfcpuBackend._build_field_index."""

    def test_build_field_index_skips_non_dict_forms(self) -> None:
        """Test _build_field_index skips forms that are not dicts."""
        backend = PdfcpuBackend()
        data = {"forms": ["not-a-dict"]}
        exact, suffix = backend._build_field_index(data)
        assert exact == {}
        assert suffix == {}

    def test_build_field_index_skips_non_list_entries(self) -> None:
        """Test _build_field_index skips entry values that are not lists."""
        backend = PdfcpuBackend()
        data = {"forms": [{"textfield": "not-a-list"}]}
        exact, suffix = backend._build_field_index(data)
        assert exact == {}
        assert suffix == {}

    def test_build_field_index_skips_non_dict_entries(self) -> None:
        """Test _build_field_index skips entries that are not dicts."""
        backend = PdfcpuBackend()
        data = {"forms": [{"textfield": ["not-a-dict"]}]}
        exact, suffix = backend._build_field_index(data)
        assert exact == {}
        assert suffix == {}

    def test_build_field_index_continues_when_no_field_id(self) -> None:
        """Test _build_field_index continues when field name is missing."""
        backend = PdfcpuBackend()
        data = {"forms": [{"textfield": [{"id": "1"}]}]}
        exact, suffix = backend._build_field_index(data)
        assert exact == {"1": ("textfield", {"id": "1"})}
        assert suffix == {}

    def test_build_field_index_accepts_name_without_field_id(self) -> None:
        """Test _build_field_index indexes fields that have a name but no id."""
        backend = PdfcpuBackend()
        entry = {"name": "form.section.Name"}
        data = {"forms": [{"textfield": [entry]}]}

        exact, suffix = backend._build_field_index(data)

        assert exact == {"form.section.Name": ("textfield", entry)}
        assert suffix == {"Name": ("textfield", entry)}


class TestPdfcpuBackendMergeFormData:
    """Tests for PdfcpuBackend._merge_form_data."""

    def test_merge_form_data_checkbox_conversion(self) -> None:
        """Test _merge_form_data converts booleans for checkboxes."""
        backend = PdfcpuBackend()
        pdfcpu_data = {
            "forms": [
                {
                    "checkbox": [
                        {"id": "Agree", "name": "Agree", "value": False},
                    ]
                }
            ]
        }
        result = backend._merge_form_data(pdfcpu_data, {"Agree": True})
        assert result["forms"][0]["checkbox"][0]["value"] is True

    def test_merge_form_data_listbox_with_list(self) -> None:
        """Test _merge_form_data handles listbox with list values."""
        backend = PdfcpuBackend()
        pdfcpu_data = {
            "forms": [
                {
                    "listbox": [
                        {"id": "Colors", "name": "Colors", "value": ""},
                    ]
                }
            ]
        }
        result = backend._merge_form_data(pdfcpu_data, {"Colors": ["Red", "Blue"]})
        field = result["forms"][0]["listbox"][0]
        assert field.get("value") is None
        assert field["values"] == ["Red", "Blue"]

    def test_merge_form_data_listbox_with_scalar(self) -> None:
        """Test _merge_form_data handles listbox with scalar value."""
        backend = PdfcpuBackend()
        pdfcpu_data = {
            "forms": [
                {
                    "listbox": [
                        {"id": "Colors", "name": "Colors", "values": ["Red", "Blue"]},
                    ]
                }
            ]
        }
        result = backend._merge_form_data(pdfcpu_data, {"Colors": "Green"})
        field = result["forms"][0]["listbox"][0]
        assert field["value"] == "Green"
        assert field.get("values") is None

    def test_merge_form_data_skips_unknown_fields(self) -> None:
        """Test _merge_form_data ignores fields not present in pdfcpu data."""
        backend = PdfcpuBackend()
        pdfcpu_data = {"forms": [{"textfield": [{"id": "Name", "name": "Name", "value": ""}]}]}
        result = backend._merge_form_data(pdfcpu_data, {"Unknown": "value"})
        assert result["forms"][0]["textfield"][0]["value"] == ""


class TestPdfcpuBackendFillForm:
    """Tests for PdfcpuBackend.fill_form."""

    def test_fill_form_binary_not_found(self, tmp_path: PathType) -> None:
        """Test fill_form raises when pdfcpu binary is not found."""
        backend = PdfcpuBackend()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake")

        with (
            patch("privacyforms_pdf.backends.pdfcpu.shutil.which", return_value=None),
            pytest.raises(PDFFormError, match="pdfcpu binary not found: pdfcpu"),
        ):
            backend.fill_form(pdf_file, {"Name": "John"})

    def test_fill_form_missing_output_file(self, tmp_path: PathType) -> None:
        """Test fill_form raises when pdfcpu does not create output file."""
        backend = PdfcpuBackend()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake")
        output_file = tmp_path / "output.pdf"

        with (
            patch("privacyforms_pdf.backends.pdfcpu.shutil.which", return_value="/usr/bin/pdfcpu"),
            patch.object(backend, "_export_form_data", return_value={"forms": []}),
            patch.object(backend, "_run_command") as mock_run,
        ):
            mock_run.return_value = None
            with pytest.raises(PDFFormError, match="pdfcpu did not create output file"):
                backend.fill_form(pdf_file, {"Name": "John"}, output_file)

    def test_fill_form_success(self, tmp_path: PathType) -> None:
        """Test fill_form succeeds."""
        backend = PdfcpuBackend()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake")
        output_file = tmp_path / "output.pdf"

        with (
            patch("privacyforms_pdf.backends.pdfcpu.shutil.which", return_value="/usr/bin/pdfcpu"),
            patch.object(backend, "_export_form_data", return_value={"forms": []}),
            patch.object(backend, "_run_command") as mock_run,
        ):
            mock_run.return_value = None
            output_file.touch()
            result = backend.fill_form(pdf_file, {"Name": "John"}, output_file)
            assert result == output_file


class TestPdfcpuBackendShouldFallback:
    """Tests for PdfcpuBackend._should_fallback."""

    def test_should_fallback_missing_da(self) -> None:
        """Test _should_fallback returns True for missing DA entry."""
        assert (
            PdfcpuBackend._should_fallback("dict=formFieldDict required entry=DA missing") is True
        )

    def test_should_fallback_panic_attack(self) -> None:
        """Test _should_fallback returns True for panic attack."""
        assert PdfcpuBackend._should_fallback("unexpected panic attack") is True

    def test_should_fallback_other_error(self) -> None:
        """Test _should_fallback returns False for unrelated errors."""
        assert PdfcpuBackend._should_fallback("some other error") is False


class TestIsPdfcpuAvailable:
    """Tests for is_pdfcpu_available helper."""

    def test_is_pdfcpu_available_true(self) -> None:
        """Test is_pdfcpu_available returns True when binary exists."""
        with patch("privacyforms_pdf.backends.pdfcpu.shutil.which", return_value="/usr/bin/pdfcpu"):
            assert is_pdfcpu_available() is True

    def test_is_pdfcpu_available_false(self) -> None:
        """Test is_pdfcpu_available returns False when binary is missing."""
        with patch("privacyforms_pdf.backends.pdfcpu.shutil.which", return_value=None):
            assert is_pdfcpu_available() is False
