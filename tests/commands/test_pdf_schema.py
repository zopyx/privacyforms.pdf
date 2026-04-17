"""Tests for pdf-forms schema command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from privacyforms_pdf.cli import main


class TestSchemaCommand:
    """Tests for schema command."""

    def test_schema_success_with_output(self, tmp_path: Path) -> None:
        """Test schema command writes JSON schema output file."""
        runner = CliRunner()
        output = tmp_path / "out.json"
        result = runner.invoke(main, ["schema", str(output)])

        assert result.exit_code == 0
        assert output.exists()
        text = output.read_text()
        assert '"$defs"' in text or '"$ref"' in text or "PDFRepresentation" in text
        assert "title" in text

    def test_schema_default_output(self, tmp_path: Path) -> None:
        """Test schema command uses default output path."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as isolated_dir:
            result = runner.invoke(main, ["schema"])
            assert result.exit_code == 0
            default_output = Path(isolated_dir) / "pdfrepresentation-schema.json"
            assert default_output.exists()

    def test_schema_with_dash_o_option(self, tmp_path: Path) -> None:
        """Test schema command writes JSON output file using -o option."""
        runner = CliRunner()
        output = tmp_path / "out.json"
        result = runner.invoke(main, ["schema", "-o", str(output)])

        assert result.exit_code == 0
        assert output.exists()
        text = output.read_text()
        assert "title" in text

    def test_schema_refuses_symlink_output(self, tmp_path: Path) -> None:
        """Test schema command refuses to write to a symlink output path."""
        runner = CliRunner()
        real_file = tmp_path / "real.json"
        symlink_output = tmp_path / "out.json"
        symlink_output.symlink_to(real_file)

        result = runner.invoke(main, ["schema", "-o", str(symlink_output)])

        assert result.exit_code != 0
        assert "Refusing to write to symlink" in result.output
