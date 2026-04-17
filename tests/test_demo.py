"""Tests for the demo fill_sample script."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the demo module directly (it manipulates sys.path internally)
from demo.fill_sample import generate_sample_value, main


class TestGenerateSampleValue:
    """Tests for generate_sample_value."""

    def test_checkbox(self) -> None:
        """It returns True for checkbox fields."""
        assert generate_sample_value("checkbox", "Agree") is True

    def test_datefield(self) -> None:
        """It returns a fixed date string for datefield fields."""
        assert generate_sample_value("datefield", "Date") == "2026-03-07"

    def test_radiobuttongroup(self) -> None:
        """It returns a placeholder option for radio button groups."""
        assert generate_sample_value("radiobuttongroup", "Status") == "Option1"

    def test_textfield_default(self) -> None:
        """It returns a sample string for text and other field types."""
        assert generate_sample_value("textfield", "Name") == "Sample Name"


class TestMain:
    """Tests for the main entry point."""

    def test_pdf_not_found(self, tmp_path: Path) -> None:
        """It returns 1 when the sample PDF is missing."""
        with patch("demo.fill_sample.Path") as mock_path_cls:
            mock_pdf = MagicMock()
            mock_pdf.exists.return_value = False
            mock_pdf.__str__ = lambda self: "samples/FilledForm.pdf"
            mock_path_cls.side_effect = lambda p: (
                mock_pdf if p == "samples/FilledForm.pdf" else Path(p)
            )
            assert main() == 1

    def test_pdf_without_form(self, tmp_path: Path) -> None:
        """It returns 1 when the PDF has no form."""
        extractor_mock = MagicMock()
        extractor_mock.has_form.return_value = False

        with (
            patch("demo.fill_sample.Path") as mock_path_cls,
            patch("demo.fill_sample.PDFFormExtractor", return_value=extractor_mock),
        ):
            mock_pdf = MagicMock()
            mock_pdf.exists.return_value = True
            mock_path_cls.side_effect = lambda p: (
                mock_pdf if p == "samples/FilledForm.pdf" else Path(p)
            )
            assert main() == 1

    def test_success_flow(self, tmp_path: Path) -> None:
        """It extracts fields, writes JSON, fills form, and verifies output."""
        extractor_mock = MagicMock()
        extractor_mock.has_form.return_value = True
        extractor_mock.fill_form_from_json.return_value = Path("filled.pdf")

        fake_field = MagicMock()
        fake_field.name = "Name"
        fake_field.type = "textfield"
        fake_field.value = "Sample Name"

        representation_mock = MagicMock()
        representation_mock.fields = [fake_field]

        filled_rep_mock = MagicMock()
        filled_rep_mock.fields = [fake_field]

        def parse_pdf_side_effect(path: str | Path) -> MagicMock:
            p = Path(path)
            if p.name == "filled.pdf":
                return filled_rep_mock
            return representation_mock

        json_data: dict[str, str] = {}

        def dump_side_effect(data: object, fp: object, **kwargs: object) -> None:
            nonlocal json_data
            json_data = data  # type: ignore[assignment]

        with (
            patch("demo.fill_sample.Path") as mock_path_cls,
            patch("demo.fill_sample.PDFFormExtractor", return_value=extractor_mock),
            patch("demo.fill_sample.parse_pdf", side_effect=parse_pdf_side_effect),
            patch("builtins.open", MagicMock()),
            patch("json.dump", side_effect=dump_side_effect),
            patch("json.dumps", return_value="{}"),
        ):
            mock_pdf = MagicMock()
            mock_pdf.exists.return_value = True
            mock_pdf.__str__ = lambda self: "samples/FilledForm.pdf"
            mock_path_cls.side_effect = lambda p: (
                mock_pdf if p == "samples/FilledForm.pdf" else Path(p)
            )
            assert main() == 0
            assert json_data == {"Name": "Sample Name"}
            extractor_mock.fill_form_from_json.assert_called_once()

    def test_fill_exception(self, tmp_path: Path) -> None:
        """It returns 1 when form filling raises an exception."""
        extractor_mock = MagicMock()
        extractor_mock.has_form.return_value = True
        extractor_mock.fill_form_from_json.side_effect = RuntimeError("fill failed")

        fake_field = MagicMock()
        fake_field.name = "Name"
        fake_field.type = "textfield"

        representation_mock = MagicMock()
        representation_mock.fields = [fake_field]

        with (
            patch("demo.fill_sample.Path") as mock_path_cls,
            patch("demo.fill_sample.PDFFormExtractor", return_value=extractor_mock),
            patch("demo.fill_sample.parse_pdf", return_value=representation_mock),
            patch("builtins.open", MagicMock()),
            patch("json.dump"),
            patch("json.dumps", return_value="{}"),
        ):
            mock_pdf = MagicMock()
            mock_pdf.exists.return_value = True
            mock_path_cls.side_effect = lambda p: (
                mock_pdf if p == "samples/FilledForm.pdf" else Path(p)
            )
            assert main() == 1
