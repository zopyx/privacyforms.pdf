"""Tests for pdf-forms parse command."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from click.testing import CliRunner

from privacyforms_pdf.cli import main
from privacyforms_pdf.schema import FieldLayout, PDFField, PDFRepresentation, RowGroup

if TYPE_CHECKING:
    from pathlib import Path


class TestParseCommand:
    """Tests for parse command."""

    def test_parse_success_with_output(self, tmp_path: Path) -> None:
        """Test parse command writes JSON output file."""
        runner = CliRunner()
        pdf_file = tmp_path / "form.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        with patch("privacyforms_pdf.commands.pdf_parse.extract_pdf_form") as mock_extract:
            mock_extract.return_value = PDFRepresentation(
                spec_version="1.0", source="form.pdf", fields=[], rows=[]
            )
            output = tmp_path / "out.json"
            result = runner.invoke(main, ["parse", str(pdf_file), str(output)])

        assert result.exit_code == 0
        assert output.exists()
        assert "form.pdf" in output.read_text()

    def test_parse_default_output(self, tmp_path: Path) -> None:
        """Test parse command uses default output path."""
        runner = CliRunner()
        pdf_file = tmp_path / "form.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        with patch("privacyforms_pdf.commands.pdf_parse.extract_pdf_form") as mock_extract:
            mock_extract.return_value = PDFRepresentation(
                spec_version="1.0", source="form.pdf", fields=[], rows=[]
            )
            result = runner.invoke(main, ["parse", str(pdf_file)])

        assert result.exit_code == 0
        default_output = tmp_path / "form.json"
        assert default_output.exists()

    def test_parse_by_id(self, tmp_path: Path) -> None:
        """Test parse command with --by-id flag."""
        runner = CliRunner()
        pdf_file = tmp_path / "form.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        field = PDFField(
            name="Name",
            id="f-0",
            type="textfield",
            layout=FieldLayout(page=1, x=0, y=0, width=10, height=10),
        )
        representation = PDFRepresentation(
            source="form.pdf",
            fields=[field],
            rows=[RowGroup(fields=[field], page_index=1)],
        )

        with patch(
            "privacyforms_pdf.commands.pdf_parse.extract_pdf_form",
            return_value=representation,
        ):
            result = runner.invoke(main, ["parse", str(pdf_file), "--by-id"])

        assert result.exit_code == 0
        assert "f-0" in result.output

    def test_parse_value_error(self, tmp_path: Path) -> None:
        """Test parse command handles ValueError."""
        runner = CliRunner()
        pdf_file = tmp_path / "form.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        with patch(
            "privacyforms_pdf.commands.pdf_parse.extract_pdf_form",
            side_effect=ValueError("too large"),
        ):
            result = runner.invoke(main, ["parse", str(pdf_file)])

        assert result.exit_code != 0
        assert "too large" in result.output

    def test_parse_with_dash_o_option(self, tmp_path: Path) -> None:
        """Test parse command writes JSON output file using -o option."""
        runner = CliRunner()
        pdf_file = tmp_path / "form.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        with patch("privacyforms_pdf.commands.pdf_parse.extract_pdf_form") as mock_extract:
            mock_extract.return_value = PDFRepresentation(
                spec_version="1.0", source="form.pdf", fields=[], rows=[]
            )
            output = tmp_path / "out.json"
            result = runner.invoke(main, ["parse", str(pdf_file), "-o", str(output)])

        assert result.exit_code == 0
        assert output.exists()
        assert "form.pdf" in output.read_text()

    def test_parse_refuses_symlink_output(self, tmp_path: Path) -> None:
        """Test parse command refuses to write to a symlink output path."""
        runner = CliRunner()
        pdf_file = tmp_path / "form.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        real_file = tmp_path / "real.json"
        symlink_output = tmp_path / "out.json"
        symlink_output.symlink_to(real_file)

        with patch("privacyforms_pdf.commands.pdf_parse.extract_pdf_form") as mock_extract:
            mock_extract.return_value = PDFRepresentation(
                spec_version="1.0", source="form.pdf", fields=[], rows=[]
            )
            result = runner.invoke(main, ["parse", str(pdf_file), "-o", str(symlink_output)])

        assert result.exit_code != 0
        assert "Refusing to write to symlink" in result.output
